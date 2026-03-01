"""
WordPress article parser for rogerdeakins.com blog content.

Handles the "Looking at Lighting" (LAL) series and any other article series
with the same WordPress Page structure.

Key functions:
- discover_article_urls(html, base_url)  -- find ALL article URLs from the nav menu
- discover_lal_urls(html, base_url)      -- find /lal-*/ URLs only (kept for compat)
- parse_article_page(html, url)          -- extract content from a WordPress article page
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

# Site-structure paths to EXCLUDE from article discovery.
# Anything not in this set that is a top-level slug with a hyphen is
# treated as a potential article and scraped.
_EXCLUDE_PATHS = {
    "forums",
    "lighting",
    "filmography",
    "members",
    "members-only",
    "contact",
    "store",
    "byways",
    "byways-press",
    "byways_giveaway",
    "team-deakins-podcast-2",
    "registration-query",
    "website-questionsideas",
    "terms-of-use",
    "link-page",
    "rad",
    "reflections",
    "wp-login.php",
    "wp-admin",
    "feed",
    "sitemap.xml",
}


@dataclass(frozen=True)
class RawArticle:
    """Parsed article data extracted from a WordPress page."""

    url: str
    article_slug: str  # e.g., "lal-sicario-tunnel-and-alejandros-revenge"
    series: str  # e.g., "lal"
    wp_post_id: str | None  # WordPress post ID from article element ID (e.g., "post-1234")
    title: str
    author_name: str | None
    date_published: str | None  # ISO 8601, from JSON-LD or <time> element
    date_modified: str | None  # ISO 8601, from JSON-LD
    description: str | None  # Meta description or JSON-LD description
    featured_image_url: str | None
    content_text: str  # Plain text of article body (nav stripped)
    content_html: str  # Raw HTML of article body (nav stripped)
    is_restricted: bool  # True if WP-Members gate detected (not logged in)


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
        "prisoners-1"                                 -> "prisoners"
        "bladerunner-2049-police-station"             -> "bladerunner"
        "skyfall-1"                                   -> "skyfall"
        "tmwwt-bank"                                  -> "tmwwt"
    """
    prefix_map = [
        ("lal-", "lal"),
        ("looking-at-lighting", "lal-early"),
        ("roger-deakins-looks-at-lighting", "lal-early"),
        ("empire-of-light", "empire-of-light"),
        ("prisoners", "prisoners"),
        ("bladerunner", "bladerunner"),
        ("br-", "bladerunner"),
        ("blade-runner", "bladerunner"),
        ("hail-caesar", "hail-caesar"),
        ("jesse-james", "jesse-james"),
        ("skyfall", "skyfall"),
        ("spectre-", "spectre"),
        ("ncfom", "ncfom"),
        ("no-country", "ncfom"),
        ("tmwwt-", "tmwwt"),
        ("unbroken-", "unbroken"),
        ("1984-", "1984"),
        ("true-grit", "true-grit"),
        ("1917-", "1917"),
        ("sicario-", "sicario"),
    ]
    for prefix, series in prefix_map:
        if slug.startswith(prefix):
            return series
    # Strip trailing -N to get base series name
    base = re.sub(r"-\d+$", "", slug)
    return base if base else "blog"


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


def _strip_nav_elements(content_el) -> None:
    """
    Remove navigation/index elements from the content element in-place.

    The rogerdeakins.com articles embed a TablePress table at the end of
    every article that lists all other articles in the series. This is
    navigation, not content. We also strip any standalone nav wrappers.
    """
    # TablePress plugin: <table class="tablepress ...">
    for table in content_el.find_all("table", class_=re.compile(r"tablepress")):
        table.decompose()

    # Any surrounding <div class="tablepress-table-description"> or similar
    for div in content_el.find_all("div", class_=re.compile(r"tablepress")):
        div.decompose()

    # WP-Members restriction forms
    for rm in content_el.find_all(id=re.compile(r"wpmem")):
        rm.decompose()


def discover_article_urls(html: str, base_url: str) -> list[str]:
    """
    Parse all links on the page for article URLs (any series).

    Strategy: include all same-domain top-level paths (no subdirectory slash)
    that are NOT in the explicit exclusion list and contain a hyphen
    (all article slugs are hyphenated; site-section pages are single words).

    Returns a deduplicated, sorted list of absolute article URLs.
    """
    soup = BeautifulSoup(html, "html.parser")
    found: set[str] = set()
    # base_netloc may be "rogerdeakins.com" while links use "www.rogerdeakins.com"
    base_netloc = urlparse(base_url).netloc.lstrip("www.")

    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if not href or href.startswith("#") or href.startswith("mailto:"):
            continue
        abs_url = urljoin(base_url, href)
        parsed = urlparse(abs_url)

        # Only same-domain (handles www. prefix mismatch)
        if parsed.netloc and base_netloc not in parsed.netloc:
            continue

        path = parsed.path.strip("/")

        # Skip paths with a subdirectory (forum topics, WP pages etc.)
        if "/" in path:
            continue

        # Skip empty and excluded paths
        if not path or path in _EXCLUDE_PATHS:
            continue

        # All article slugs contain a hyphen; single-word paths are site sections
        if "-" not in path and "_" not in path:
            continue

        # Skip wp-* paths
        if path.startswith("wp-") or path.startswith("feed"):
            continue

        found.add(abs_url.rstrip("/") + "/")

    return sorted(found)


def discover_lal_urls(html: str, base_url: str) -> list[str]:
    """
    Parse the site navigation menu for /lal-*/ article links only.

    Kept for backward compatibility. Use discover_article_urls() for broader discovery.
    """
    soup = BeautifulSoup(html, "html.parser")
    found: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if not href:
            continue
        abs_url = urljoin(base_url, href)
        path = urlparse(abs_url).path.strip("/")
        if path.startswith("lal-"):
            found.add(abs_url.rstrip("/") + "/")

    return sorted(found)


def discover_series_urls(html: str, base_url: str, series_prefix: str) -> list[str]:
    """Generic article URL discovery by path prefix."""
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
    Strips navigation tables (TablePress) embedded in .entry-content.
    """
    soup = BeautifulSoup(html, "html.parser")
    article_slug = _slug_from_url(url)
    series = _series_from_slug(article_slug)

    # --- Auth check: WP-Members restriction gate ---
    is_restricted = bool(
        soup.find(id="wpmem_restricted_msg") or soup.find(id="wpmem_login_form") or soup.find(class_="wpmem_restricted")
    )

    # --- WordPress post ID from article element ---
    wp_post_id: str | None = None
    article_el = soup.find("article")
    if article_el:
        el_id = article_el.get("id", "")
        m = re.match(r"post-(\d+)", el_id)
        if m:
            wp_post_id = m.group(1)

    # --- Title: prefer og:title or JSON-LD over .entry-title (which may be
    #     the page slug rather than the readable article title) ---
    title = ""
    og_title = soup.find("meta", property="og:title")
    if og_title:
        title = og_title.get("content", "").strip()
    if not title:
        title_el = soup.find(class_="entry-title") or soup.find("h1")
        if title_el:
            title = title_el.get_text(" ", strip=True)
    if not title:
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else article_slug

    # --- JSON-LD metadata (richer than HTML elements) ---
    ld = _extract_json_ld(soup)
    date_published: str | None = ld.get("datePublished")
    date_modified: str | None = ld.get("dateModified")
    description: str | None = ld.get("description")
    featured_image_url: str | None = None

    # JSON-LD image can be a string or object
    ld_image = ld.get("image")
    if isinstance(ld_image, str):
        featured_image_url = ld_image
    elif isinstance(ld_image, dict):
        featured_image_url = ld_image.get("url")
    elif isinstance(ld_image, list) and ld_image:
        first = ld_image[0]
        featured_image_url = first if isinstance(first, str) else first.get("url")

    # --- Fallback: og:image ---
    if not featured_image_url:
        og_img = soup.find("meta", property="og:image")
        if og_img:
            featured_image_url = og_img.get("content") or None

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

    # --- Author ---
    author_name: str | None = None
    author_el = soup.find(class_="author") or soup.find(rel="author")
    if author_el:
        author_name = author_el.get_text(" ", strip=True) or None
    if not author_name and ld.get("author"):
        author_data = ld["author"]
        if isinstance(author_data, dict):
            author_name = author_data.get("name")
        elif isinstance(author_data, list) and author_data:
            author_name = author_data[0].get("name") if isinstance(author_data[0], dict) else None

    # --- Content: strip nav tables before extracting ---
    content_html = ""
    content_text = ""

    content_el = soup.find(class_="entry-content")
    if content_el:
        _strip_nav_elements(content_el)
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
