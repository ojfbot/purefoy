"""
Articles scraping pipeline orchestrator.

Glues together authentication, parsing, image downloading, and storage.
"""

import hashlib
from datetime import datetime
from typing import Optional, List, Dict
from urllib.parse import urljoin

from .auth import WordPressAuthHandler
from .config import ArticlesSettings
from .image_downloader import ImageDownloader
from .models import (
    ArticleLeaf,
    ArticleIds,
    ArticleMetadata,
    Author,
    Image,
    Link,
    Provenance,
    HttpProvenance,
    Integrity,
    FilmSectionLeaf,
    ArticleRef,
    ArticlesIndexLeaf,
)
from .parser import parse_articles_menu, parse_article_page
from .store import ArticleJsonStore


class ArticlesPipeline:
    """
    High-level orchestration for articles scraping.

    Coordinates:
    - Authentication (WordPressAuthHandler)
    - HTML fetching and parsing
    - Image downloading
    - JSON persistence
    - Progress tracking
    """

    def __init__(
        self,
        settings: ArticlesSettings,
        auth_handler: WordPressAuthHandler,
        store: ArticleJsonStore,
        image_downloader: ImageDownloader,
    ):
        """
        Initialize pipeline.

        Args:
            settings: ArticlesSettings configuration
            auth_handler: Authenticated WordPressAuthHandler
            store: ArticleJsonStore for persistence
            image_downloader: ImageDownloader for images
        """
        self.settings = settings
        self.auth = auth_handler
        self.store = store
        self.images = image_downloader

        # Get authenticated session for requests
        self.session = self.auth.get_authenticated_session()

    def scrape_articles_menu(self) -> List[Dict[str, any]]:
        """
        Discover all films and article URLs from the navigation menu.

        Returns:
            List of film dicts with articles
        """
        print("Discovering articles from navigation menu...")

        # Fetch any page to get the navigation menu
        # Using the main "Looking at Lighting" page if it exists
        menu_url = "https://www.rogerdeakins.com"

        try:
            response = self.session.get(menu_url, timeout=30)
            response.raise_for_status()

            # Parse menu
            from .parser import parse_articles_menu
            films = parse_articles_menu(self.settings.base_url, response.text)

            print(f"✓ Discovered {len(films)} films with articles")

            # Convert to dict for easier handling
            films_data = []
            for film in films:
                films_data.append({
                    "film_title": film.film_title,
                    "film_slug": film.film_slug,
                    "articles": [
                        {
                            "title": article.title,
                            "url": article.url,
                            "slug": article.article_slug,
                        }
                        for article in film.articles
                    ],
                })

            return films_data

        except Exception as e:
            print(f"✗ Error discovering articles: {e}")
            return []

    def scrape_article(
        self,
        article_url: str,
        film_slug: Optional[str] = None,
        skip_if_exists: bool = True,
    ) -> Optional[ArticleLeaf]:
        """
        Scrape a single article.

        Args:
            article_url: URL of the article
            film_slug: Film this article belongs to (optional, will be inferred)
            skip_if_exists: Skip if article already exists and unchanged

        Returns:
            ArticleLeaf or None if failed
        """
        try:
            print(f"\n  Scraping: {article_url}")

            # Parse URL to get article slug
            from urllib.parse import urlparse
            parsed = urlparse(article_url)
            article_slug = parsed.path.strip("/").split("/")[-1]
            article_id = article_slug

            # Check if already exists
            if skip_if_exists and self.store.article_exists(article_id):
                print(f"    ✓ Already scraped (skipping)")
                return self.store.read_article(article_id)

            # Fetch HTML
            response = self.session.get(article_url, timeout=30)
            response.raise_for_status()

            # Parse article
            raw_article = parse_article_page(
                base_url=self.settings.base_url,
                article_url=article_url,
                html=response.text
            )

            # Use provided film_slug or inferred one
            if not film_slug:
                film_slug = raw_article.film_slug

            print(f"    Title: {raw_article.title}")
            print(f"    Film: {film_slug}")
            print(f"    Images: {len(raw_article.raw_images)}")

            # Download images
            images = []
            if self.settings.download_images and raw_article.raw_images:
                print(f"    Downloading {len(raw_article.raw_images)} images...")

                for img_data in raw_article.raw_images:
                    img_url = img_data["src"]
                    result = self.images.download_image(img_url)

                    if result.success:
                        images.append(Image(
                            src_url=img_url,
                            local_path=str(result.local_path.relative_to(self.settings.out_dir)) if result.local_path else None,
                            alt_text=img_data.get("alt"),
                            caption=img_data.get("caption"),
                            width=img_data.get("width"),
                            height=img_data.get("height"),
                            size_bytes=result.size_bytes,
                        ))
                    else:
                        # Still record the image URL even if download failed
                        images.append(Image(
                            src_url=img_url,
                            alt_text=img_data.get("alt"),
                            caption=img_data.get("caption"),
                            width=img_data.get("width"),
                            height=img_data.get("height"),
                        ))

            # Extract links
            links = [
                Link(
                    href=link_data["href"],
                    text=link_data["text"],
                    is_internal=link_data["is_internal"],
                    title=link_data.get("title"),
                )
                for link_data in raw_article.raw_links
            ]

            # Calculate content hash
            content_hash = hashlib.sha256(raw_article.content_text.encode()).hexdigest()[:16]

            # Create ArticleLeaf
            article = ArticleLeaf(
                ids=ArticleIds(
                    article_id=article_id,
                    film_slug=film_slug,
                    article_slug=article_slug,
                    article_url=article_url,
                ),
                metadata=ArticleMetadata(
                    title=raw_article.title,
                    description=raw_article.description,
                    author=Author(display_name=raw_article.author_name),
                    published_date=raw_article.published_date,
                    modified_date=raw_article.modified_date,
                    featured_image=Image(src_url=raw_article.featured_image_url) if raw_article.featured_image_url else None,
                    word_count=len(raw_article.content_text.split()),
                    tags=raw_article.tags,
                    categories=raw_article.categories,
                ),
                content_html=raw_article.content_html,
                content_text=raw_article.content_text,
                blocks=[],  # TODO: Extract structured blocks if needed
                images=images,
                links=links,
                quotes=[],  # TODO: Extract quotes if needed
                provenance=Provenance(
                    source_url=article_url,
                    scraped_at=datetime.now().isoformat(),
                    scraper_version="1.0.0",
                    http=HttpProvenance(
                        status_code=response.status_code,
                        etag=response.headers.get("etag"),
                        last_modified=response.headers.get("last-modified"),
                        content_length=len(response.text),
                    ),
                ),
                integrity=Integrity(
                    content_hash=content_hash,
                    parser_version="1.0.0",
                ),
            )

            # Persist
            self.store.write_article(article)
            print(f"    ✓ Saved to: articles/{article_id}.json")

            return article

        except Exception as e:
            print(f"    ✗ Error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def scrape_film(
        self,
        film_slug: str,
        film_title: str,
        articles: List[Dict[str, str]],
        max_articles: int = 0,
    ) -> Optional[FilmSectionLeaf]:
        """
        Scrape all articles for a film.

        Args:
            film_slug: Film identifier
            film_title: Film display name
            articles: List of article dicts with 'url', 'slug', 'title'
            max_articles: Maximum articles to scrape (0 = unlimited)

        Returns:
            FilmSectionLeaf or None if failed
        """
        print(f"\n{'=' * 70}")
        print(f"Scraping film: {film_title}")
        print(f"{'=' * 70}")

        articles_to_scrape = articles[:max_articles] if max_articles > 0 else articles

        print(f"Articles: {len(articles_to_scrape)}/{len(articles)}")

        scraped_articles = []
        for i, article_data in enumerate(articles_to_scrape, 1):
            print(f"\n[{i}/{len(articles_to_scrape)}]", end=" ")

            article_leaf = self.scrape_article(
                article_url=article_data["url"],
                film_slug=film_slug,
            )

            if article_leaf:
                scraped_articles.append(article_leaf)

        # Create article refs
        article_refs = [
            ArticleRef(
                article_id=article.ids.article_id,
                article_slug=article.ids.article_slug,
                article_url=article.ids.article_url,
                title=article.metadata.title,
                description=article.metadata.description,
                published_date=article.metadata.published_date,
            )
            for article in scraped_articles
        ]

        # Calculate total images
        total_images = sum(len(article.images) for article in scraped_articles)

        # Create FilmSectionLeaf
        film_section = FilmSectionLeaf(
            film_id=film_slug,
            film_slug=film_slug,
            film_title=film_title,
            description=f"Lighting analysis articles for {film_title}",
            article_refs=article_refs,
            article_count=len(article_refs),
            total_images=total_images,
            scraped_at=datetime.now().isoformat(),
            source_menu_url=self.settings.base_url,
        )

        # Persist
        self.store.write_film(film_section)

        print(f"\n✓ Film complete: {len(scraped_articles)} articles, {total_images} images")

        return film_section

    def scrape_all_articles(
        self,
        max_films: int = 0,
        max_articles_per_film: int = 0,
    ) -> ArticlesIndexLeaf:
        """
        Scrape all articles from all films.

        Args:
            max_films: Maximum films to scrape (0 = unlimited)
            max_articles_per_film: Maximum articles per film (0 = unlimited)

        Returns:
            ArticlesIndexLeaf with complete index
        """
        print("=" * 70)
        print("SCRAPING ALL ARTICLES")
        print("=" * 70)

        # Discover articles
        films_data = self.scrape_articles_menu()

        if not films_data:
            print("✗ No articles discovered")
            return None

        # Limit films if requested
        films_to_scrape = films_data[:max_films] if max_films > 0 else films_data

        print(f"\nFilms to scrape: {len(films_to_scrape)}/{len(films_data)}")

        # Scrape each film
        film_sections = []
        for i, film_data in enumerate(films_to_scrape, 1):
            print(f"\n{'#' * 70}")
            print(f"FILM {i}/{len(films_to_scrape)}")
            print(f"{'#' * 70}")

            film_section = self.scrape_film(
                film_slug=film_data["film_slug"],
                film_title=film_data["film_title"],
                articles=film_data["articles"],
                max_articles=max_articles_per_film,
            )

            if film_section:
                film_sections.append(film_section)

        # Create articles index
        total_articles = sum(film.article_count for film in film_sections)
        total_images = sum(film.total_images for film in film_sections)

        # Generate content hash
        content = "|".join(sorted(film.film_slug for film in film_sections))
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

        index = ArticlesIndexLeaf(
            films=film_sections,
            total_films=len(film_sections),
            total_articles=total_articles,
            total_images=total_images,
            scraped_at=datetime.now().isoformat(),
            source_url=self.settings.base_url,
            content_hash=content_hash,
        )

        # Persist index
        self.store.write_articles_index(index)

        print("\n" + "=" * 70)
        print("SCRAPING COMPLETE")
        print("=" * 70)
        print(f"Films:    {len(film_sections)}")
        print(f"Articles: {total_articles}")
        print(f"Images:   {total_images}")
        print("=" * 70)

        return index


# ============================================================================
# Convenience Functions
# ============================================================================

def build_pipeline(settings: ArticlesSettings) -> ArticlesPipeline:
    """
    Build a complete pipeline from settings.

    Args:
        settings: ArticlesSettings configuration

    Returns:
        Configured ArticlesPipeline ready to use
    """
    from .auth import authenticate_from_settings

    # Ensure directories
    settings.ensure_directories()

    # Authenticate
    auth_handler = authenticate_from_settings(settings)

    # Create store
    store = ArticleJsonStore(settings.out_dir)

    # Create image downloader
    image_downloader = ImageDownloader(
        images_dir=settings.images_dir,
        session=auth_handler.get_authenticated_session(),
        max_size_mb=settings.max_image_size_mb,
        allowed_formats=settings.image_formats,
        delay_s=settings.delay_s,
    )

    # Create pipeline
    pipeline = ArticlesPipeline(
        settings=settings,
        auth_handler=auth_handler,
        store=store,
        image_downloader=image_downloader,
    )

    return pipeline
