"""
WordPress article parser for rogerdeakins.com blog content.

Handles the "Looking at Lighting" (LAL) series and any other article series
with the same WordPress Page structure.

Key functions:
- discover_lal_urls(html, base_url)   -- find all /lal-*/ URLs from the nav menu
- parse_article_page(html, url)        -- extract content from a WordPress article page
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


@dataclass(frozen=True)
class RawArticle:
    """Parsed article data extracted from a WordPress page."""
    url: str
    article_slug: str           # e.g., "lal-sicario-tunnel-and-alejandros-revenge"
    series: str                 # e.g., "lal"
    wp_post_id: Optional[str]   # WordPress post ID from article element ID (e.g., "post-1234")
    title: str
    author_name: Optional[str]
    date_published: Optional[str]   # ISO 8601, from JSON-LD or <time> element
    date_modified: Optional[str]    # ISO 8601, from JSON-LD
    description: Optional[str]      # Meta description or JSON-LD description
    featured_image_url: Optional[str]
    content_text: str               # Plain text of article body
    content_html: str               # Raw HTML of article body
    is_restricted: bool             # True if WP-Members gate detected (not logged in)


def _slug_from_url(url: str) -> str:
    """Extract the last non-empty path segment as a slug."""
    path = urlparse(url).path.rstrip("/")
    return path.split("/")[-1] if path else "unknown"


def _series_from_slug(slug: str) -> str:
    """
    Derive a series identifier from the article slug.

    Examples:
        "lal-sicario-tunnel-and-alejandros-revenge"  -> "lal"
        "empire-of-light-lighting"                    -> "empire-of-light"
    """
    if slug.startswith("lal-"):
        return "lal"
    # Add more series as discovered
    return "blog"


def _extract_json_ld(soup: BeautifulSoup) -> dict:
    """Extract the first Yoast JSON-LD schema object (if present)."""
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            # Yoast wraps everything in a @graph array
            if isinstance(data, dict) and "@graph" in data:
                # Find the WebPage or Article node
                for node in data["@graph"]:
                    if node.get("@type") in ("WebPage", "Article", "BlogPosting"):
                        return node
            elif isinstance(data, dict):
                return data
        except (json.JSONDecodeError, AttributeError):
            continue
    return {}


def discover_lal_urls(html: str, base_url: str) -> list[str]:
    """
    Parse the site navigation menu for /lal-*/ article links.

    The main nav menu is public (no auth required) and lists all LAL articles
    as submenu items under "Looking at Lighting".

    Returns a deduplicated, sorted list of absolute article URLs.
    """
    soup = BeautifulSoup(html, "html.parser")
    found: set[str] = set()

    # Primary: site header nav menu
    nav_candidates = [
        soup.select("#site-header-menu-primary a"),
        soup.select("nav a"),
        soup.select(".menu a"),
        soup.select("ul.menu a"),
    ]

    for links in nav_candidates:
        for a in links:
            href = a.get("href", "")
            if not href:
                continue
            abs_url = urljoin(base_url, href)
            path = urlparse(abs_url).path.strip("/")
            # Match /lal-*/ pattern
            if path.startswith("lal-") or re.match(r"lal-.+", path):
                found.add(abs_url.rstrip("/") + "/")

    # Fallback: any anchor link containing /lal- in the href
    if not found:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/lal-" in href:
                abs_url = urljoin(base_url, href)
                found.add(abs_url.rstrip("/") + "/")

    return sorted(found)


def discover_series_urls(html: str, base_url: str, series_prefix: str) -> list[str]:
    """
    Generic version of discover_lal_urls for other series.

    Args:
        series_prefix: URL path prefix to match, e.g. "empire-of-light"
    """
    soup = BeautifulSoup(html, "html.parser")
    found: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        abs_url = urljoin(base_url, href)
        path = urlparse(abs_url).path.strip("/")
        if path.startswith(series_prefix):
            found.add(abs_url.rstrip("/") + "/")

    return sorted(found)


def parse_article_page(html: str, url: str) -> RawArticle:
    """
    Extract structured content from a WordPress article page.

    Handles both authenticated (full content) and restricted (login wall) states.
    """
    soup = BeautifulSoup(html, "html.parser")
    article_slug = _slug_from_url(url)
    series = _series_from_slug(article_slug)

    # --- Auth check: WP-Members restriction gate ---
    is_restricted = bool(
        soup.find(id="wpmem_restricted_msg")
        or soup.find(id="wpmem_login_form")
        or soup.find(class_="wpmem_restricted")
    )

    # --- WordPress post ID from article element ---
    wp_post_id: Optional[str] = None
    article_el = soup.find("article")
    if article_el:
        el_id = article_el.get("id", "")
        m = re.match(r"post-(\d+)", el_id)
        if m:
            wp_post_id = m.group(1)

    # --- Title ---
    title = ""
    title_el = soup.find(class_="entry-title") or soup.find("h1")
    if title_el:
        title = title_el.get_text(" ", strip=True)
    if not title:
        og_title = soup.find("meta", property="og:title")
        if og_title:
            title = og_title.get("content", "").strip()
    if not title:
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else article_slug

    # --- JSON-LD metadata (richer than HTML elements) ---
    ld = _extract_json_ld(soup)
    date_published: Optional[str] = ld.get("datePublished")
    date_modified: Optional[str] = ld.get("dateModified")
    description: Optional[str] = ld.get("description")
    featured_image_url: Optional[str] = None

    # JSON-LD image can be a string or object
    ld_image = ld.get("image")
    if isinstance(ld_image, str):
        featured_image_url = ld_image
    elif isinstance(ld_image, dict):
        featured_image_url = ld_image.get("url")
    elif isinstance(ld_image, list) and ld_image:
        first = ld_image[0]
        featured_image_url = first if isinstance(first, str) else first.get("url")

    # --- Fallback: <time> element for date ---
    if not date_published:
        time_el = soup.find("time", class_="entry-date")
        if time_el:
            date_published = time_el.get("datetime") or time_el.get_text(strip=True) or None

    # --- Fallback: meta description ---
    if not description:
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            description = meta_desc.get("content", "").strip() or None
        if not description:
            og_desc = soup.find("meta", property="og:description")
            if og_desc:
                description = og_desc.get("content", "").strip() or None

    # --- Fallback: featured image from og:image ---
    if not featured_image_url:
        og_img = soup.find("meta", property="og:image")
        if og_img:
            featured_image_url = og_img.get("content") or None

    # --- Author ---
    author_name: Optional[str] = None
    author_el = soup.find(class_="author") or soup.find(rel="author")
    if author_el:
        author_name = author_el.get_text(" ", strip=True) or None
    if not author_name and ld.get("author"):
        author_data = ld["author"]
        if isinstance(author_data, dict):
            author_name = author_data.get("name")
        elif isinstance(author_data, list) and author_data:
            author_name = author_data[0].get("name") if isinstance(author_data[0], dict) else None

    # --- Content ---
    content_html = ""
    content_text = ""

    content_el = soup.find(class_="entry-content")
    if content_el:
        # Remove the WP-Members restriction form if present (not content)
        for rm in content_el.find_all(id=re.compile(r"wpmem")):
            rm.decompose()
        content_html = str(content_el)
        content_text = content_el.get_text("\n", strip=True)
    elif is_restricted:
        content_text = "[MEMBER-ONLY CONTENT — authentication required]"
        content_html = content_text

    return RawArticle(
        url=url,
        article_slug=article_slug,
        series=series,
        wp_post_id=wp_post_id,
        title=title,
        author_name=author_name,
        date_published=date_published,
        date_modified=date_modified,
        description=description,
        featured_image_url=featured_image_url,
        content_text=content_text,
        content_html=content_html,
        is_restricted=is_restricted,
    )
