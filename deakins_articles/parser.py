"""
HTML parser for Roger Deakins articles.

Extracts structured data from:
1. Articles index/menu (film hierarchy)
2. Individual article pages (content, images, metadata)
"""

import re
from typing import List, Tuple, Optional, Dict, Any
from urllib.parse import urljoin, urlparse
from datetime import datetime

from bs4 import BeautifulSoup, Tag

from .models import (
    RawArticle,
    FilmMenuItem,
    ArticleMenuItem,
)


# ============================================================================
# Articles Index/Menu Parsing
# ============================================================================

def parse_articles_menu(base_url: str, html: str) -> List[FilmMenuItem]:
    """
    Parse the "Looks at Lighting" navigation menu to extract film hierarchy.

    The menu structure is:
    <ul class="sub-menu">
        <li class="menu-item menu-item-has-children">
            <a href="#">Film Title</a>
            <ul class="sub-menu">
                <li><a href="...">Article Title</a></li>
                ...
            </ul>
        </li>
        ...
    </ul>

    Args:
        base_url: Site base URL for resolving relative links
        html: HTML content containing the menu

    Returns:
        List of FilmMenuItem objects with nested articles
    """
    soup = BeautifulSoup(html, "html.parser")
    films = []

    # Find the "Looking at Lighting" section
    # This could be in the main menu or a dedicated page
    # Look for menu items with sub-menus containing article links

    # Strategy: find all <li> elements that have children and contain article links
    film_items = soup.find_all("li", class_=re.compile(r"menu-item-has-children"))

    for film_li in film_items:
        # Get film title from the first <a> tag
        film_link = film_li.find("a", recursive=False)
        if not film_link:
            continue

        film_title = film_link.get_text(strip=True)

        # Skip if this is not a film section (e.g., has a real URL)
        film_href = film_link.get("href", "")
        if film_href and film_href != "#" and "rogerdeakins.com" in film_href:
            # This is a direct article link, not a film section
            continue

        # Find the nested <ul> with articles
        articles_ul = film_li.find("ul", class_="sub-menu")
        if not articles_ul:
            continue

        # Extract articles
        articles = []
        for article_li in articles_ul.find_all("li", class_="menu-item", recursive=False):
            article_link = article_li.find("a")
            if not article_link:
                continue

            article_url = article_link.get("href", "")
            if not article_url or article_url == "#":
                continue

            # Resolve relative URLs
            article_url = urljoin(base_url, article_url)

            article_title = article_link.get_text(strip=True)

            # Extract slug from URL
            parsed = urlparse(article_url)
            article_slug = parsed.path.strip("/").split("/")[-1]

            articles.append(
                ArticleMenuItem(
                    title=article_title,
                    url=article_url,
                    article_slug=article_slug,
                )
            )

        if articles:
            # Generate film slug from title
            film_slug = _slugify(film_title)

            films.append(
                FilmMenuItem(
                    film_title=film_title,
                    film_slug=film_slug,
                    articles=articles,
                )
            )

    return films


def parse_articles_index_page(base_url: str, html: str) -> Tuple[List[FilmMenuItem], str]:
    """
    Parse a dedicated "Looks at Lighting" index page.

    Args:
        base_url: Site base URL
        html: Page HTML

    Returns:
        Tuple of (films list, page description)
    """
    soup = BeautifulSoup(html, "html.parser")

    # Extract films from menu or page content
    films = parse_articles_menu(base_url, html)

    # Extract page description
    description = ""
    description_elem = soup.find("div", class_="entry-content")
    if description_elem:
        # Get first paragraph
        first_p = description_elem.find("p")
        if first_p:
            description = first_p.get_text(strip=True)

    return films, description


# ============================================================================
# Individual Article Parsing
# ============================================================================

def parse_article_page(base_url: str, article_url: str, html: str) -> RawArticle:
    """
    Parse an individual article page to extract all content.

    Args:
        base_url: Site base URL
        article_url: Full URL of the article
        html: Article page HTML

    Returns:
        RawArticle with extracted content
    """
    soup = BeautifulSoup(html, "html.parser")

    # Extract article slug and ID from URL
    parsed_url = urlparse(article_url)
    article_slug = parsed_url.path.strip("/").split("/")[-1]

    # Try to extract WordPress post ID from body classes
    article_id = _extract_post_id(soup) or article_slug

    # Infer film slug from article slug (common patterns)
    film_slug = _infer_film_slug(article_slug)

    # Extract title
    title = _extract_title(soup)

    # Extract content
    content_html, content_text = _extract_content(soup)

    # Extract metadata
    author_name = _extract_author(soup)
    published_date = _extract_date(soup, "published")
    modified_date = _extract_date(soup, "modified")

    # Extract images
    raw_images = _extract_images(soup, base_url)
    featured_image_url = _extract_featured_image(soup, base_url)

    # Extract links
    raw_links = _extract_links(soup, base_url)

    # Extract SEO metadata
    description = _extract_meta_description(soup)
    tags = _extract_tags(soup)
    categories = _extract_categories(soup)

    return RawArticle(
        article_id=article_id,
        film_slug=film_slug,
        article_slug=article_slug,
        article_url=article_url,
        title=title,
        description=description,
        content_html=content_html,
        content_text=content_text,
        author_name=author_name,
        published_date=published_date,
        modified_date=modified_date,
        raw_images=raw_images,
        raw_links=raw_links,
        featured_image_url=featured_image_url,
        tags=tags,
        categories=categories,
    )


# ============================================================================
# Content Extraction Helpers
# ============================================================================

def _extract_title(soup: BeautifulSoup) -> str:
    """Extract article title from WordPress theme structure."""
    # WordPress theme uses: <h1 class="entry-title"><a>Title Here</a></h1>
    title_elem = soup.find("h1", class_="entry-title")
    if title_elem:
        # Title may be in <a> tag within h1
        link = title_elem.find("a")
        if link:
            title = link.get_text(strip=True)
        else:
            title = title_elem.get_text(strip=True)

        if title:
            # Clean up title (remove site name if present)
            title = re.sub(r"\s*[-–|]\s*Roger Deakins.*$", "", title, flags=re.IGNORECASE)
            return title

    # Fallback: extract from <title> meta tag
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)
        # Clean up site name
        title = re.sub(r"\s*[-–|]\s*Roger Deakins.*$", "", title, flags=re.IGNORECASE)
        return title

    return "Untitled Article"


def _extract_content(soup: BeautifulSoup) -> Tuple[str, str]:
    """
    Extract article content in both HTML and plain text.

    Returns:
        Tuple of (content_html, content_text)
    """
    # Find main content area
    content_area = soup.find("div", class_=re.compile(r"entry-content")) or \
                   soup.find("article", class_=re.compile(r"post")) or \
                   soup.find("main")

    if not content_area:
        return "", ""

    # Get HTML (prettified)
    content_html = str(content_area)

    # Get plain text
    content_text = content_area.get_text(separator="\n", strip=True)

    return content_html, content_text


def _extract_author(soup: BeautifulSoup) -> str:
    """Extract author name from WordPress theme structure."""
    # WordPress theme uses: <span class="author vcard"><a>Author Name</a></span>
    author_elem = soup.find("span", class_="author") or \
                  soup.find("span", class_="vcard")

    if author_elem:
        # Author name may be in <a> tag
        link = author_elem.find("a", rel="author")
        if link:
            return link.get_text(strip=True)
        return author_elem.get_text(strip=True)

    # Fallback: meta tag
    meta = soup.find("meta", {"name": "author"})
    if meta:
        return meta.get("content", "Unknown")

    return "Unknown"


def _extract_date(soup: BeautifulSoup, date_type: str = "published") -> Optional[str]:
    """
    Extract publication or modification date from WordPress theme.

    Args:
        soup: BeautifulSoup object
        date_type: "published" or "modified"

    Returns:
        ISO 8601 date string or None
    """
    # WordPress theme uses: <time class="entry-date updated" datetime="...">
    if date_type == "published":
        time_elem = soup.find("time", class_="entry-date")
    else:
        time_elem = soup.find("time", class_="updated")

    if time_elem:
        datetime_attr = time_elem.get("datetime")
        if datetime_attr:
            return _normalize_date(datetime_attr)

        text = time_elem.get_text(strip=True)
        return _normalize_date(text)

    # Fallback: meta tags
    meta_selectors = {
        "published": ["article:published_time", "datePublished"],
        "modified": ["article:modified_time", "dateModified"],
    }

    for prop in meta_selectors.get(date_type, []):
        meta = soup.find("meta", {"property": prop}) or \
               soup.find("meta", {"itemprop": prop})
        if meta:
            date_str = meta.get("content")
            if date_str:
                return _normalize_date(date_str)

    return None


def _extract_images(soup: BeautifulSoup, base_url: str) -> List[Dict[str, Any]]:
    """
    Extract all images from article content (WordPress theme structure).

    WordPress uses <div class="wp-caption"> with <p class="wp-caption-text"> for captions,
    NOT <figure>/<figcaption> tags.
    """
    images = []

    # Find content area
    content_area = soup.find("div", class_="entry-content")
    if not content_area:
        return images

    # Look for wp-caption divs (preferred - has captions)
    for wp_caption_div in content_area.find_all("div", class_="wp-caption"):
        img = wp_caption_div.find("img")
        if not img:
            continue

        src = img.get("src") or img.get("data-src")
        if not src:
            continue

        # Resolve relative URLs
        src = urljoin(base_url, src)

        # Extract metadata
        alt_text = img.get("alt", "")
        width = img.get("width")
        height = img.get("height")

        # Extract srcset for responsive images
        srcset = img.get("srcset", "")

        # Get caption from <p class="wp-caption-text">
        caption = None
        caption_p = wp_caption_div.find("p", class_="wp-caption-text")
        if caption_p:
            caption = caption_p.get_text(strip=True)

        images.append({
            "src": src,
            "alt": alt_text,
            "caption": caption,
            "width": int(width) if width and width.isdigit() else None,
            "height": int(height) if height and height.isdigit() else None,
            "srcset": srcset,
        })

    # Also capture any standalone images not in wp-caption divs
    for img in content_area.find_all("img"):
        # Skip if already processed via wp-caption
        if img.find_parent("div", class_="wp-caption"):
            continue

        src = img.get("src") or img.get("data-src")
        if not src:
            continue

        src = urljoin(base_url, src)
        alt_text = img.get("alt", "")
        width = img.get("width")
        height = img.get("height")
        srcset = img.get("srcset", "")

        images.append({
            "src": src,
            "alt": alt_text,
            "caption": None,
            "width": int(width) if width and width.isdigit() else None,
            "height": int(height) if height and height.isdigit() else None,
            "srcset": srcset,
        })

    return images


def _extract_featured_image(soup: BeautifulSoup, base_url: str) -> Optional[str]:
    """Extract featured/hero image URL from meta tags."""
    # WordPress theme uses twitter:image meta tag
    twitter_image = soup.find("meta", {"name": "twitter:image"})
    if twitter_image:
        src = twitter_image.get("content")
        if src:
            return urljoin(base_url, src)

    # Fallback: og:image
    og_image = soup.find("meta", {"property": "og:image"})
    if og_image:
        src = og_image.get("content")
        if src:
            return urljoin(base_url, src)

    # Last resort: first image in content
    content_area = soup.find("div", class_="entry-content")
    if content_area:
        first_img = content_area.find("img")
        if first_img:
            src = first_img.get("src") or first_img.get("data-src")
            if src:
                return urljoin(base_url, src)

    return None


def _extract_links(soup: BeautifulSoup, base_url: str) -> List[Dict[str, Any]]:
    """Extract all links from article content."""
    links = []

    content_area = soup.find("div", class_=re.compile(r"entry-content"))
    if not content_area:
        return links

    for a in content_area.find_all("a", href=True):
        href = a.get("href")
        if not href or href.startswith("#"):
            continue

        href = urljoin(base_url, href)
        text = a.get_text(strip=True)
        title = a.get("title")

        # Determine if internal or external
        is_internal = urlparse(href).netloc == urlparse(base_url).netloc

        links.append({
            "href": href,
            "text": text,
            "title": title,
            "is_internal": is_internal,
        })

    return links


def _extract_meta_description(soup: BeautifulSoup) -> Optional[str]:
    """Extract meta description or excerpt."""
    meta = soup.find("meta", {"name": "description"}) or \
           soup.find("meta", {"property": "og:description"})

    if meta:
        return meta.get("content")

    # Try excerpt
    excerpt = soup.find("div", class_=re.compile(r"excerpt"))
    if excerpt:
        return excerpt.get_text(strip=True)

    return None


def _extract_tags(soup: BeautifulSoup) -> List[str]:
    """Extract article tags."""
    tags = []

    # WordPress typically uses <a rel="tag"> for tags
    tag_links = soup.find_all("a", rel="tag")
    for tag_link in tag_links:
        tags.append(tag_link.get_text(strip=True))

    return tags


def _extract_categories(soup: BeautifulSoup) -> List[str]:
    """Extract article categories."""
    categories = []

    # Look for category links
    cat_links = soup.find_all("a", rel="category") or \
                soup.find_all("a", class_=re.compile(r"category"))

    for cat_link in cat_links:
        categories.append(cat_link.get_text(strip=True))

    return categories


def _extract_post_id(soup: BeautifulSoup) -> Optional[str]:
    """Extract WordPress post ID from body classes."""
    body = soup.find("body")
    if not body:
        return None

    classes = body.get("class", [])
    for cls in classes:
        if cls.startswith("postid-"):
            return cls.replace("postid-", "")

    return None


# ============================================================================
# Utility Functions
# ============================================================================

def _slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    # Remove special characters, convert to lowercase
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    # Replace spaces with hyphens
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug.strip("-")


def _infer_film_slug(article_slug: str) -> str:
    """
    Infer film slug from article slug.

    Examples:
    - "lal-br2049-sappers-farm" → "bladerunner-2049"
    - "skyfall-1" → "skyfall"
    - "hail-caesar-calvary" → "hail-caesar"
    """
    # Remove common prefixes
    slug = re.sub(r"^(lal-|looking-at-lighting-)", "", article_slug)

    # Common abbreviations
    abbrev_map = {
        "br2049": "bladerunner-2049",
        "br-": "bladerunner-2049-",
        "ncfom": "no-country-for-old-men",
        "tmwwt": "the-man-who-wasnt-there",
        "hp-": "hudsucker-proxy-",
    }

    for abbrev, full in abbrev_map.items():
        if slug.startswith(abbrev):
            return full.rstrip("-")

    # Extract first significant part before numbers or detailed scene descriptions
    parts = slug.split("-")

    # Remove trailing scene-specific parts (like numbers, scene names)
    # Keep first 1-3 significant words
    significant_parts = []
    for part in parts:
        # Stop at numbers or very specific scene words
        if part.isdigit():
            break
        if part in ["int", "ext", "scene", "part", "pt", "seq"]:
            break

        significant_parts.append(part)

        # Stop after getting film title (usually 1-3 words)
        if len(significant_parts) >= 3:
            break

    return "-".join(significant_parts) if significant_parts else slug


def _normalize_date(date_str: str) -> str:
    """Normalize various date formats to ISO 8601."""
    if not date_str:
        return None

    # Try parsing various formats
    formats = [
        "%Y-%m-%dT%H:%M:%S%z",  # ISO 8601 with timezone
        "%Y-%m-%dT%H:%M:%S",  # ISO 8601 without timezone
        "%Y-%m-%d",  # Date only
        "%B %d, %Y",  # "January 15, 2026"
        "%b %d, %Y",  # "Jan 15, 2026"
        "%d %B %Y",  # "15 January 2026"
        "%m/%d/%Y",  # "01/15/2026"
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return dt.isoformat()
        except ValueError:
            continue

    # If all parsing fails, return original
    return date_str
