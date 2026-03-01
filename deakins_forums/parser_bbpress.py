"""
bbPress-like parser for rogerdeakins.com forums.

The rogerdeakins.com forums are exposed under /forums/ with forum pages like:
- /forums/forum/team-deakins/ (includes subforums + topic list + "Viewing ..." pagination)
Topic pages like:
- /forums/topic/gaining-set-experience/ (posts show '#<id>' tokens)

This module does NOT write files. It only extracts structured Python objects.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

FORUM_INDEX_RE = re.compile(r"^/forums/?$")
FORUM_URL_RE = re.compile(r"^/forums/forum/([^/]+)/?$")
TOPIC_URL_RE = re.compile(r"^/forums/topic/([^/]+)/?$")
REPLY_URL_RE = re.compile(r"^/forums/reply/(\d+)/?$")

POST_ID_RE = re.compile(r"#(?P<id>\d{3,})\b")
PAGINATION_RE = re.compile(
    r"Viewing\s+\d+\s+(?:topics?|replies?)\s+-\s+(\d+)\s+through\s+(\d+)\s+\(of\s+(\d+)\s+total\)", re.IGNORECASE
)


@dataclass(frozen=True)
class ForumRef:
    url: str
    slug: str
    title: str


@dataclass(frozen=True)
class TopicRef:
    url: str
    slug: str
    title: str
    started_by: str | None = None


@dataclass(frozen=True)
class RawPost:
    post_id: str
    author: str | None
    role: str | None
    timestamp_raw: str | None
    content_text: str
    content_html: str | None
    reply_permalink: str | None

    # NEW: Threading information
    post_type: str = "topic"  # "topic" or "reply"
    parent_post_id: str | None = None  # ID of post this replies to
    parent_type: str | None = None  # "topic" or "reply"
    position: int | None = None  # Reply position within thread


@dataclass(frozen=True)
class PaginationInfo:
    """Pagination metadata extracted from forum/topic pages."""

    current_start: int
    current_end: int
    total_items: int
    has_next: bool


def parse_forums_index(base_url: str, html: str) -> list[ForumRef]:
    """Parse /forums/ and return forum references."""
    soup = BeautifulSoup(html, "html.parser")
    container = soup.find(id="bbpress-forums") or soup

    out: dict[str, ForumRef] = {}
    for a in container.select('a[href*="/forums/forum/"]'):
        href = a.get("href") or ""
        full = urljoin(base_url, href)
        m = FORUM_URL_RE.match(urlparse(full).path)
        if not m:
            continue
        title = a.get_text(" ", strip=True)
        if not title:
            continue
        slug = m.group(1)
        out[full] = ForumRef(url=full, slug=slug, title=title)

    return list(out.values())


def extract_pagination(soup: BeautifulSoup) -> PaginationInfo | None:
    """Extract pagination info from 'Viewing X topics/replies - Y through Z (of N total)' text."""
    text = soup.get_text(" ", strip=True)
    m = PAGINATION_RE.search(text)
    if not m:
        return None

    start = int(m.group(1))
    end = int(m.group(2))
    total = int(m.group(3))

    return PaginationInfo(current_start=start, current_end=end, total_items=total, has_next=end < total)


def find_next_page_url(base_url: str, soup: BeautifulSoup, current_url: str) -> str | None:
    """Find the 'Next' pagination link."""
    # Look for pagination links
    for a in soup.find_all("a", href=True):
        link_text = a.get_text(strip=True).lower()
        if "next" in link_text or "→" in a.get_text():
            return urljoin(base_url, a["href"])

    # Also check for /page/N/ pattern
    parsed = urlparse(current_url)
    path_parts = parsed.path.rstrip("/").split("/")

    # Check if we're already on a page
    page_num = 1
    if "page" in path_parts:
        try:
            idx = path_parts.index("page")
            if idx + 1 < len(path_parts):
                page_num = int(path_parts[idx + 1])
        except (ValueError, IndexError):
            pass

    # Check pagination info to see if there's a next page
    pagination = extract_pagination(soup)
    if pagination and pagination.has_next:
        # Construct next page URL
        base_path = parsed.path.rstrip("/")
        if f"/page/{page_num}" in base_path:
            base_path = base_path.replace(f"/page/{page_num}", f"/page/{page_num + 1}")
        else:
            base_path = f"{base_path}/page/{page_num + 1}"
        return f"{parsed.scheme}://{parsed.netloc}{base_path}/"

    return None


def parse_forum_page(
    base_url: str, forum_slug: str, html: str
) -> tuple[list[ForumRef], list[TopicRef], PaginationInfo | None]:
    """
    Parse a forum page.

    Returns
    -------
    subforums:
        Any subforum references listed on the page (Team Deakins has them).
    topics:
        Topic references found in the topic list table.
    pagination:
        Pagination metadata if present.
    """
    soup = BeautifulSoup(html, "html.parser")
    container = soup.find(id="bbpress-forums") or soup

    # Subforums: other /forums/forum/<slug>/ links on the page
    subforums: dict[str, ForumRef] = {}
    for a in container.select('a[href*="/forums/forum/"]'):
        href = a.get("href") or ""
        full = urljoin(base_url, href)
        m = FORUM_URL_RE.match(urlparse(full).path)
        if not m:
            continue
        slug = m.group(1)
        if slug == forum_slug:
            continue
        title = a.get_text(" ", strip=True)
        if title:
            subforums[full] = ForumRef(url=full, slug=slug, title=title)

    # Topics: /forums/topic/<slug>/, typically near "Started by:"
    topics: dict[str, TopicRef] = {}
    for a in container.select('a[href*="/forums/topic/"]'):
        href = a.get("href") or ""
        full = urljoin(base_url, href)
        m = TOPIC_URL_RE.match(urlparse(full).path)
        if not m:
            continue
        slug = m.group(1)
        title = a.get_text(" ", strip=True)
        if not title:
            continue

        row = a.find_parent(["tr", "li", "div"])
        row_text = row.get_text(" ", strip=True) if row else ""
        started_by = None
        if "Started by:" in row_text:
            # best-effort
            sb = re.search(r"Started by:\s*([^\n]+)", row_text)
            if sb:
                started_by = sb.group(1).strip()

        topics[full] = TopicRef(url=full, slug=slug, title=title, started_by=started_by)

    pagination = extract_pagination(container)

    return list(subforums.values()), list(topics.values()), pagination


def parse_topic_page(base_url: str, html: str) -> tuple[str | None, list[RawPost], PaginationInfo | None]:
    """
    Parse a topic page and return title + RawPost list + pagination.

    This uses resilient heuristics based on the user-visible layout where each
    post begins with a timestamp line containing '#<id>' tokens.
    """
    soup = BeautifulSoup(html, "html.parser")
    # Use broader container to include both article and bbpress-forums divs
    # The article with #XXXXX text is often outside bbpress-forums
    container = soup.find(id="content") or soup.find(id="main") or soup

    h = soup.find(["h1", "h2"])
    title = h.get_text(" ", strip=True) if h else None

    # Candidate nodes: Look for the main post container nodes
    # These have either:
    # - id="post-XXXXX" attribute (topic starters)
    # - class containing "post-XXXXX" AND "loop-item" (replies)
    # We prioritize these over inner divs that just contain #XXXXX in text
    candidates = []
    seen_post_ids_in_containers = set()

    # First pass: Find container divs with id="post-XXXXX" or class="post-XXXXX"
    all_nodes = container.find_all(["article", "li", "div"])
    for node in all_nodes:
        node_classes = node.get("class", [])

        # Check for post-XXXXX class (but skip header divs for class check)
        if isinstance(node_classes, list):
            # Skip class check for header divs (they don't have useful classes)
            # but don't skip the whole node - they may have id="post-X"
            is_header = any(
                cls in ["bbp-reply-header", "bbp-topic-header"] for cls in node_classes if isinstance(cls, str)
            )
            if not is_header:
                # Check for post-XXXXX class
                for cls in node_classes:
                    if isinstance(cls, str) and cls.startswith("post-"):
                        post_id = cls.replace("post-", "")
                        if post_id.isdigit():
                            candidates.append(node)
                            seen_post_ids_in_containers.add(post_id)
                            break

        # Also check id="post-XXXXX" attribute
        # Note: This catches header divs with id="post-X" (important for replies!)
        # Don't skip if already in seen - we want to collect multiple nodes per post
        node_id = node.get("id", "")
        if node_id and node_id.startswith("post-"):
            post_id = node_id.replace("post-", "")
            if post_id.isdigit():
                candidates.append(node)
                seen_post_ids_in_containers.add(post_id)

    # Second pass: If we didn't find enough candidates, fall back to text search
    # (This handles edge cases where the HTML structure is different)
    if len(candidates) < 2:  # Expecting at least a topic + reply usually
        for node in container.find_all(["article", "li", "div"]):
            node_classes = node.get("class", [])
            if isinstance(node_classes, list):
                is_header = any(
                    cls in ["bbp-reply-header", "bbp-topic-header"] for cls in node_classes if isinstance(cls, str)
                )
                if is_header:
                    continue

            txt = node.get_text(" ", strip=True)
            if POST_ID_RE.search(txt):
                # Extract post ID to avoid duplicates
                pid_m = POST_ID_RE.search(txt)
                if pid_m:
                    post_id = pid_m.group("id")
                    if post_id not in seen_post_ids_in_containers:
                        candidates.append(node)

    # De-duplicate candidates: if we have multiple divs for the same post ID,
    # prefer the one with the most structure (loop-item class with parent info)
    post_to_nodes: dict[str, list] = {}
    for node in candidates:
        # Extract post ID from the node's id attribute OR from classes
        post_id = None

        # Try id attribute first
        node_id = node.get("id", "")
        if node_id and node_id.startswith("post-"):
            post_id = node_id.replace("post-", "")

        # If no id attribute, try classes
        if not post_id:
            node_classes = node.get("class", [])
            if isinstance(node_classes, list):
                for cls in node_classes:
                    if isinstance(cls, str) and cls.startswith("post-"):
                        post_id = cls.replace("post-", "")
                        break

        # Fallback: extract from text (least reliable)
        if not post_id:
            node_text = node.get_text(" ", strip=True)
            pid_m = POST_ID_RE.search(node_text)
            if pid_m:
                post_id = pid_m.group("id")

        if post_id:
            if post_id not in post_to_nodes:
                post_to_nodes[post_id] = []
            post_to_nodes[post_id].append(node)

    # For each post, we may have multiple nodes (e.g., <article> and <div>)
    # - The <article> has the "#XXXXX" text
    # - The <div class="loop-item-X"> has parent relationship classes
    # Strategy: Use article for text, merge classes from all nodes for parent info
    posts: list[RawPost] = []
    seen: set[str] = set()

    for post_id, nodes in post_to_nodes.items():
        if post_id in seen:
            continue
        seen.add(post_id)

        # Choose the best node for content extraction
        # Priority: loop-item div (has correct author/content) > article (has #XXXXX but may have wrong content)
        extraction_node = None

        # First, try to find a loop-item div (best source for content)
        for node in nodes:
            node_classes = node.get("class", [])
            if isinstance(node_classes, list):
                has_loop_item = any(isinstance(cls, str) and cls.startswith("loop-item") for cls in node_classes)
                if has_loop_item:
                    extraction_node = node
                    break

        # If no loop-item, find node with "#XXXXX" text (fallback to article)
        if not extraction_node:
            for node in nodes:
                text = node.get_text(" ", strip=True)
                if POST_ID_RE.search(text):
                    extraction_node = node
                    break

        if not extraction_node:
            continue

        # Extract text from extraction node (for #XXXXX verification if needed)
        node_text_lines = [
            line.strip() for line in extraction_node.get_text("\n", strip=True).splitlines() if line.strip()
        ]

        # Merge all classes from ALL candidate nodes to get parent info
        all_classes = []
        for node in nodes:
            node_classes = node.get("class", [])
            if isinstance(node_classes, list):
                all_classes.extend(node_classes)
            elif isinstance(node_classes, str):
                all_classes.append(node_classes)

        # reply permalink if present
        reply_permalink = None
        for a in extraction_node.find_all("a", href=True):
            full = urljoin(base_url, a["href"])
            rm = REPLY_URL_RE.match(urlparse(full).path)
            if rm:
                reply_permalink = full
                break

        # Extract post type from merged classes (type-topic or type-reply)
        post_type = "topic"  # default
        if "type-reply" in all_classes:
            post_type = "reply"
        elif "type-topic" in all_classes:
            post_type = "topic"

        # Extract parent relationship from bbp-parent-* classes
        parent_post_id = None
        parent_type = None
        for cls in all_classes:
            if isinstance(cls, str):
                if cls.startswith("bbp-parent-topic-"):
                    parent_post_id = cls.replace("bbp-parent-topic-", "")
                    parent_type = "topic"
                    break  # Found parent, no need to continue
                elif cls.startswith("bbp-parent-reply-"):
                    parent_post_id = cls.replace("bbp-parent-reply-", "")
                    parent_type = "reply"
                    break

        # Extract position from bbp-reply-position-N classes
        position = None
        for cls in all_classes:
            if isinstance(cls, str) and cls.startswith("bbp-reply-position-"):
                try:
                    position = int(cls.replace("bbp-reply-position-", ""))
                    break
                except ValueError:
                    pass

        # Extract timestamp from dedicated date element (more reliable than heuristics)
        timestamp_raw = None
        date_elem = extraction_node.select_one(".bbp-topic-post-date, .bbp-reply-post-date")
        if date_elem:
            timestamp_raw = date_elem.get_text(strip=True)

        # Fallback: heuristic timestamp extraction from text lines
        if not timestamp_raw:
            if node_text_lines and len(node_text_lines) > 0:
                if " at " in node_text_lines[0] and f"#{post_id}" in node_text_lines[0]:
                    timestamp_raw = node_text_lines[0]

        # Extract author using CSS selectors (more reliable than positional heuristics)
        author = None
        author_elem = extraction_node.select_one(".bbp-author-name")
        if author_elem:
            author = author_elem.get_text(strip=True)

        # Extract role using CSS selectors
        role = None
        role_elem = extraction_node.select_one(".bbp-author-role")
        if role_elem:
            # Role element may contain nested divs, get all text
            role = role_elem.get_text(strip=True)

        # Extract content from the content container
        content_text = ""
        content_html = None

        # Try to find the content container
        content_container = extraction_node.select_one(".bbp-topic-content, .bbp-reply-content")
        if content_container:
            content_text = content_container.get_text("\n", strip=True)
            # Preserve inner HTML for structured parsing later
            try:
                content_html = "".join(str(x) for x in content_container.contents).strip() or None
            except Exception:
                content_html = None
        else:
            # Fallback: use all text from node, removing metadata sections
            content_text = extraction_node.get_text("\n", strip=True)

        # Clean up content_text by removing any remaining metadata
        # (timestamps, author names that might have leaked through)
        if content_text and timestamp_raw and timestamp_raw in content_text:
            content_text = content_text.replace(timestamp_raw, "").strip()
        if content_text and author and author in content_text:
            # Be careful: author name might appear in content legitimately
            # Only remove if it's at the very beginning
            if content_text.startswith(author):
                content_text = content_text[len(author) :].strip()
        if content_text and role and role in content_text:
            if content_text.startswith(role):
                content_text = content_text[len(role) :].strip()

        posts.append(
            RawPost(
                post_id=post_id,
                author=author,
                role=role,
                timestamp_raw=timestamp_raw,
                content_text=content_text,
                content_html=content_html,
                reply_permalink=reply_permalink,
                post_type=post_type,
                parent_post_id=parent_post_id,
                parent_type=parent_type,
                position=position,
            )
        )

    pagination = extract_pagination(container)

    return title, posts, pagination
