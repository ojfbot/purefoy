"""
Content normalization utilities.

Extracts structured information from post content:
- Links (internal/external)
- Media (images, attachments)
- Quotes (with attribution)
- Content blocks (paragraphs, lists, code, etc.)
"""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .models import ContentBlock, Link, Media, Quote


def extract_links_media_quotes_blocks(
    base_url: str, content_text: str, content_html: str | None
) -> tuple[list[ContentBlock], list[Quote], list[Link], list[Media]]:
    """
    Extract structured content from post text/HTML.

    Returns
    -------
    blocks:
        Structured content blocks
    quotes:
        Extracted quotes with attribution
    links:
        Links found in content
    media:
        Media references (images, attachments)
    """
    blocks: list[ContentBlock] = []
    quotes: list[Quote] = []
    links: list[Link] = []
    media: list[Media] = []

    # If we have HTML, use it for better parsing
    if content_html:
        soup = BeautifulSoup(content_html, "html.parser")

        # Extract links
        for a in soup.find_all("a", href=True):
            href = urljoin(base_url, a["href"])
            text = a.get_text(strip=True)
            parsed = urlparse(href)
            base_parsed = urlparse(base_url)

            kind = "internal" if parsed.netloc == base_parsed.netloc else "external"
            links.append(Link(href=href, text=text, kind=kind))

        # Extract images
        for img in soup.find_all("img", src=True):
            src = urljoin(base_url, img["src"])
            alt = img.get("alt")
            media.append(Media(src=src, alt=alt, kind="image"))

        # Extract quotes (blockquote elements)
        for blockquote in soup.find_all("blockquote"):
            quote_text = blockquote.get_text("\n", strip=True)
            # Try to find attribution
            attribution = None

            # Look for common attribution patterns
            cite = blockquote.find("cite")
            if cite:
                attribution = cite.get_text(strip=True)
            else:
                # Check for "wrote:" pattern in preceding text
                prev = blockquote.find_previous_sibling()
                if prev:
                    prev_text = prev.get_text(strip=True)
                    wrote_match = re.search(r"([^\n]+)\s+wrote:", prev_text)
                    if wrote_match:
                        attribution = wrote_match.group(1).strip()

            quotes.append(Quote(text=quote_text, attributed_to=attribution))

        # Extract content blocks
        for elem in soup.find_all(["p", "blockquote", "pre", "code", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6"]):
            block_text = elem.get_text("\n", strip=True)
            if not block_text:
                continue

            if elem.name == "blockquote":
                block_type = "quote"
            elif elem.name in ["pre", "code"]:
                block_type = "code"
            elif elem.name in ["ul", "ol"]:
                block_type = "list"
            elif elem.name.startswith("h"):
                block_type = "heading"
            elif elem.name == "p":
                block_type = "paragraph"
            else:
                block_type = "unknown"

            blocks.append(ContentBlock(type=block_type, text=block_text))

    # Fallback to text-based extraction if no HTML or as supplement
    if not blocks and content_text:
        # Split into paragraphs
        paragraphs = [p.strip() for p in content_text.split("\n\n") if p.strip()]
        for para in paragraphs:
            # Detect if it looks like a quote
            if para.startswith(">") or "wrote:" in para.lower():
                # Extract quote attribution
                attribution = None
                quote_text = para
                wrote_match = re.search(r"([^\n]+)\s+wrote:", para)
                if wrote_match:
                    attribution = wrote_match.group(1).strip()
                    quote_text = para[wrote_match.end() :].strip()

                quotes.append(Quote(text=quote_text, attributed_to=attribution))
                blocks.append(ContentBlock(type="quote", text=quote_text))
            else:
                blocks.append(ContentBlock(type="paragraph", text=para))

    # Extract markdown-style links from text if no HTML
    if not links and content_text:
        # Find [text](url) patterns
        markdown_links = re.findall(r"\[([^\]]+)\]\(([^\)]+)\)", content_text)
        for text, href in markdown_links:
            full_href = urljoin(base_url, href)
            parsed = urlparse(full_href)
            base_parsed = urlparse(base_url)
            kind = "internal" if parsed.netloc == base_parsed.netloc else "external"
            links.append(Link(href=full_href, text=text, kind=kind))

        # Find plain URLs
        url_pattern = r'https?://[^\s<>"{}|\\^\[\]`]+'
        for match in re.finditer(url_pattern, content_text):
            url = match.group(0)
            parsed = urlparse(url)
            base_parsed = urlparse(base_url)
            kind = "internal" if parsed.netloc == base_parsed.netloc else "external"
            # Avoid duplicates
            if not any(link.href == url for link in links):
                links.append(Link(href=url, text=None, kind=kind))

    return blocks, quotes, links, media
