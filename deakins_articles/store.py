"""
JSON storage for articles (mirrors deakins_forums/store_json.py pattern).

Provides deterministic persistence of articles, films, and index.
"""

import json
from pathlib import Path
from typing import Optional, List, Dict, Any

from .models import ArticleLeaf, FilmSectionLeaf, ArticlesIndexLeaf


class ArticleJsonStore:
    """
    Manages JSON storage for articles with deterministic file structure.

    Directory structure:
        library/articles/
        ├── articles/<article_id>.json
        ├── films/<film_slug>.json
        └── _site/
            ├── articles_index.json
            ├── http_state.json
            └── session_cookies.json
    """

    def __init__(self, out_dir: Path):
        """
        Initialize storage.

        Args:
            out_dir: Base directory (e.g., library/articles)
        """
        self.out_dir = Path(out_dir)

        # Subdirectories
        self.articles_dir = self.out_dir / "articles"
        self.films_dir = self.out_dir / "films"
        self.site_dir = self.out_dir / "_site"

        # Ensure directories exist
        self._ensure_directories()

    def _ensure_directories(self):
        """Create necessary directories."""
        for dir_path in [self.articles_dir, self.films_dir, self.site_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

    # ========================================================================
    # Article Operations
    # ========================================================================

    def write_article(self, article: ArticleLeaf) -> Path:
        """
        Write article to JSON file.

        Args:
            article: ArticleLeaf to persist

        Returns:
            Path to written file
        """
        file_path = self.articles_dir / f"{article.ids.article_id}.json"

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(article.model_dump(), f, indent=2, ensure_ascii=False)

        return file_path

    def read_article(self, article_id: str) -> Optional[ArticleLeaf]:
        """
        Read article from JSON file.

        Args:
            article_id: Article identifier

        Returns:
            ArticleLeaf or None if not found
        """
        file_path = self.articles_dir / f"{article_id}.json"

        if not file_path.exists():
            return None

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return ArticleLeaf(**data)

    def article_exists(self, article_id: str) -> bool:
        """Check if article exists in storage."""
        file_path = self.articles_dir / f"{article_id}.json"
        return file_path.exists()

    def list_all_articles(self) -> List[str]:
        """
        List all article IDs.

        Returns:
            List of article IDs (filenames without .json)
        """
        return [f.stem for f in self.articles_dir.glob("*.json")]

    def delete_article(self, article_id: str) -> bool:
        """
        Delete an article.

        Args:
            article_id: Article to delete

        Returns:
            True if deleted, False if not found
        """
        file_path = self.articles_dir / f"{article_id}.json"

        if file_path.exists():
            file_path.unlink()
            return True

        return False

    # ========================================================================
    # Film Operations
    # ========================================================================

    def write_film(self, film: FilmSectionLeaf) -> Path:
        """
        Write film section to JSON file.

        Args:
            film: FilmSectionLeaf to persist

        Returns:
            Path to written file
        """
        file_path = self.films_dir / f"{film.film_slug}.json"

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(film.model_dump(), f, indent=2, ensure_ascii=False)

        return file_path

    def read_film(self, film_slug: str) -> Optional[FilmSectionLeaf]:
        """
        Read film section from JSON file.

        Args:
            film_slug: Film identifier

        Returns:
            FilmSectionLeaf or None if not found
        """
        file_path = self.films_dir / f"{film_slug}.json"

        if not file_path.exists():
            return None

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return FilmSectionLeaf(**data)

    def film_exists(self, film_slug: str) -> bool:
        """Check if film exists in storage."""
        file_path = self.films_dir / f"{film_slug}.json"
        return file_path.exists()

    def list_all_films(self) -> List[str]:
        """
        List all film slugs.

        Returns:
            List of film slugs (filenames without .json)
        """
        return [f.stem for f in self.films_dir.glob("*.json")]

    def delete_film(self, film_slug: str) -> bool:
        """
        Delete a film section.

        Args:
            film_slug: Film to delete

        Returns:
            True if deleted, False if not found
        """
        file_path = self.films_dir / f"{film_slug}.json"

        if file_path.exists():
            file_path.unlink()
            return True

        return False

    # ========================================================================
    # Index Operations
    # ========================================================================

    def write_articles_index(self, index: ArticlesIndexLeaf) -> Path:
        """
        Write articles index.

        Args:
            index: ArticlesIndexLeaf to persist

        Returns:
            Path to written file
        """
        file_path = self.site_dir / "articles_index.json"

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(index.model_dump(), f, indent=2, ensure_ascii=False)

        return file_path

    def read_articles_index(self) -> Optional[ArticlesIndexLeaf]:
        """
        Read articles index.

        Returns:
            ArticlesIndexLeaf or None if not found
        """
        file_path = self.site_dir / "articles_index.json"

        if not file_path.exists():
            return None

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return ArticlesIndexLeaf(**data)

    def articles_index_exists(self) -> bool:
        """Check if articles index exists."""
        file_path = self.site_dir / "articles_index.json"
        return file_path.exists()

    # ========================================================================
    # Statistics
    # ========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """
        Get storage statistics.

        Returns:
            Dict with counts and sizes
        """
        article_files = list(self.articles_dir.glob("*.json"))
        film_files = list(self.films_dir.glob("*.json"))

        article_count = len(article_files)
        film_count = len(film_files)

        # Calculate total sizes
        articles_size = sum(f.stat().st_size for f in article_files)
        films_size = sum(f.stat().st_size for f in film_files)

        # Load index if exists
        total_images = 0
        index = self.read_articles_index()
        if index:
            total_images = index.total_images

        return {
            "articles": article_count,
            "films": film_count,
            "total_images": total_images,
            "storage_mb": (articles_size + films_size) / 1024 / 1024,
        }

    def generate_report(self) -> str:
        """
        Generate a human-readable statistics report.

        Returns:
            Formatted report string
        """
        stats = self.get_stats()
        index = self.read_articles_index()

        lines = []
        lines.append("=" * 70)
        lines.append("ARTICLES STORAGE STATISTICS")
        lines.append("=" * 70)
        lines.append(f"Articles:      {stats['articles']}")
        lines.append(f"Films:         {stats['films']}")
        lines.append(f"Images:        {stats['total_images']}")
        lines.append(f"Storage:       {stats['storage_mb']:.1f} MB")

        if index:
            lines.append(f"\nLast Updated:  {index.scraped_at}")

        lines.append("=" * 70)

        return "\n".join(lines)

    # ========================================================================
    # Bulk Operations
    # ========================================================================

    def rebuild_films_from_articles(self) -> List[FilmSectionLeaf]:
        """
        Rebuild film section files from existing articles.

        Scans all articles, groups by film_slug, and creates FilmSectionLeaf files.

        Returns:
            List of created FilmSectionLeaf objects
        """
        from collections import defaultdict
        from datetime import datetime

        # Group articles by film
        films_data = defaultdict(list)

        for article_id in self.list_all_articles():
            article = self.read_article(article_id)
            if not article:
                continue

            film_slug = article.ids.film_slug

            films_data[film_slug].append({
                "article_id": article.ids.article_id,
                "article_slug": article.ids.article_slug,
                "article_url": article.ids.article_url,
                "title": article.metadata.title,
                "description": article.metadata.description,
                "published_date": article.metadata.published_date,
            })

        # Create FilmSectionLeaf for each film
        film_sections = []

        for film_slug, articles in films_data.items():
            # Derive film title from slug (capitalize, replace hyphens)
            film_title = film_slug.replace("-", " ").title()

            # Count total images across all articles
            total_images = 0
            for article_id in [a["article_id"] for a in articles]:
                article = self.read_article(article_id)
                if article:
                    total_images += len(article.images)

            # Create article refs
            from .models import ArticleRef
            article_refs = [
                ArticleRef(**article_data)
                for article_data in articles
            ]

            # Create film section
            film_section = FilmSectionLeaf(
                film_id=film_slug,
                film_slug=film_slug,
                film_title=film_title,
                description=f"Lighting analysis articles for {film_title}",
                article_refs=article_refs,
                article_count=len(articles),
                total_images=total_images,
                scraped_at=datetime.now().isoformat(),
                source_menu_url="https://www.rogerdeakins.com",
            )

            # Persist
            self.write_film(film_section)
            film_sections.append(film_section)

        return film_sections

    def rebuild_index_from_films(self) -> ArticlesIndexLeaf:
        """
        Rebuild articles index from film sections.

        Returns:
            Created ArticlesIndexLeaf
        """
        import hashlib
        from datetime import datetime

        films = []
        total_articles = 0
        total_images = 0

        for film_slug in self.list_all_films():
            film = self.read_film(film_slug)
            if not film:
                continue

            films.append(film)
            total_articles += film.article_count
            total_images += film.total_images

        # Generate content hash
        content = json.dumps([f.film_slug for f in films], sort_keys=True)
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

        # Create index
        index = ArticlesIndexLeaf(
            films=films,
            total_films=len(films),
            total_articles=total_articles,
            total_images=total_images,
            scraped_at=datetime.now().isoformat(),
            source_url="https://www.rogerdeakins.com",
            content_hash=content_hash,
        )

        # Persist
        self.write_articles_index(index)

        return index

    # ========================================================================
    # Search/Query
    # ========================================================================

    def find_articles_by_film(self, film_slug: str) -> List[ArticleLeaf]:
        """
        Find all articles for a given film.

        Args:
            film_slug: Film to search for

        Returns:
            List of ArticleLeaf objects
        """
        articles = []

        for article_id in self.list_all_articles():
            article = self.read_article(article_id)
            if article and article.ids.film_slug == film_slug:
                articles.append(article)

        return articles

    def search_articles(self, query: str) -> List[ArticleLeaf]:
        """
        Simple text search across article titles and content.

        Args:
            query: Search query (case-insensitive)

        Returns:
            List of matching ArticleLeaf objects
        """
        query_lower = query.lower()
        matches = []

        for article_id in self.list_all_articles():
            article = self.read_article(article_id)
            if not article:
                continue

            # Search in title and content
            if (query_lower in article.metadata.title.lower() or
                query_lower in article.content_text.lower()):
                matches.append(article)

        return matches
