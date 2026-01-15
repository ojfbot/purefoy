"""
Data models for Roger Deakins articles scraper.

Follows the same Pydantic-based architecture as deakins_forums
for consistency and agent-friendly structured data.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ============================================================================
# ID Models
# ============================================================================

class ArticleIds(BaseModel):
    """Unique identifiers for an article."""
    article_id: str  # Unique identifier (derived from URL or WordPress ID)
    film_slug: str  # Film/project this article belongs to
    article_slug: str  # URL-friendly article identifier
    article_url: str  # Full URL to the article

    class Config:
        frozen = True


# ============================================================================
# Content Models (reuse from forums where applicable)
# ============================================================================

class ContentBlock(BaseModel):
    """A single content block within an article."""
    type: str  # paragraph, heading, list, image, code, quote, table, etc.
    content: str
    level: Optional[int] = None  # For headings (h1=1, h2=2, etc.)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Link(BaseModel):
    """An extracted hyperlink."""
    href: str
    text: str
    is_internal: bool
    title: Optional[str] = None


class Image(BaseModel):
    """An image within the article."""
    src_url: str  # Original URL
    local_path: Optional[str] = None  # Path in library/articles/images/
    alt_text: Optional[str] = None
    caption: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    size_bytes: Optional[int] = None


class Quote(BaseModel):
    """An extracted quotation."""
    text: str
    attribution: Optional[str] = None


# ============================================================================
# Metadata Models
# ============================================================================

class Author(BaseModel):
    """Article author information."""
    display_name: str
    author_id: Optional[str] = None
    author_url: Optional[str] = None


class ArticleMetadata(BaseModel):
    """Article-specific metadata."""
    title: str
    description: Optional[str] = None
    excerpt: Optional[str] = None
    featured_image: Optional[Image] = None
    author: Author
    published_date: Optional[str] = None  # ISO 8601 format
    modified_date: Optional[str] = None  # ISO 8601 format
    word_count: int = 0
    reading_time_minutes: Optional[int] = None
    tags: List[str] = Field(default_factory=list)
    categories: List[str] = Field(default_factory=list)


# ============================================================================
# Provenance Models (mirrors forums)
# ============================================================================

class HttpProvenance(BaseModel):
    """HTTP request/response metadata."""
    status_code: int
    etag: Optional[str] = None
    last_modified: Optional[str] = None
    content_length: Optional[int] = None


class Provenance(BaseModel):
    """Provenance tracking for scraped content."""
    source_url: str
    scraped_at: str  # ISO 8601 timestamp
    scraper_version: str = "1.0.0"
    http: HttpProvenance
    query_id: Optional[str] = None  # Link to query provenance


class Integrity(BaseModel):
    """Content integrity verification."""
    content_hash: str  # SHA256 of main content
    parser_version: str = "1.0.0"
    images_hash: Optional[str] = None  # Hash of all image URLs


# ============================================================================
# Main Article Model
# ============================================================================

class ArticleLeaf(BaseModel):
    """
    Complete article representation.

    Stores everything needed to reconstruct the article for AI agents
    or export to other formats.
    """
    ids: ArticleIds
    metadata: ArticleMetadata

    # Content in multiple formats
    content_html: str  # Original HTML
    content_text: str  # Plain text extracted

    # Structured content for agent consumption
    blocks: List[ContentBlock] = Field(default_factory=list)
    images: List[Image] = Field(default_factory=list)
    links: List[Link] = Field(default_factory=list)
    quotes: List[Quote] = Field(default_factory=list)

    # Provenance and integrity
    provenance: Provenance
    integrity: Integrity

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


# ============================================================================
# Film Section Model (hierarchical grouping)
# ============================================================================

class ArticleRef(BaseModel):
    """Reference to an article within a film section."""
    article_id: str
    article_slug: str
    article_url: str
    title: str
    description: Optional[str] = None
    published_date: Optional[str] = None


class FilmSectionLeaf(BaseModel):
    """
    A film or project with associated articles.

    Example: "Blade Runner 2049" with 17 lighting breakdown articles.
    """
    film_id: str  # Unique identifier
    film_slug: str  # URL-friendly name
    film_title: str  # Display name
    description: Optional[str] = None

    # Articles within this film
    article_refs: List[ArticleRef] = Field(default_factory=list)

    # Statistics
    article_count: int = 0
    total_images: int = 0

    # Provenance
    scraped_at: str
    source_menu_url: str = "https://www.rogerdeakins.com"


# ============================================================================
# Articles Index Model (top level)
# ============================================================================

class ArticlesIndexLeaf(BaseModel):
    """
    Top-level index of all films and articles.

    Discovered from the site's "Looks at Lighting" navigation menu.
    """
    films: List[FilmSectionLeaf] = Field(default_factory=list)

    # Statistics
    total_films: int = 0
    total_articles: int = 0
    total_images: int = 0

    # Provenance
    scraped_at: str
    source_url: str = "https://www.rogerdeakins.com"
    content_hash: str  # Hash of the menu structure


# ============================================================================
# Intermediate Parsing Models
# ============================================================================

@dataclass
class RawArticle:
    """
    Intermediate representation during parsing.

    Parallels RawPost from forums scraper.
    """
    article_id: str
    film_slug: str
    article_slug: str
    article_url: str

    # Extracted content
    title: str
    description: Optional[str] = None
    content_html: str = ""
    content_text: str = ""

    # Metadata
    author_name: str = "Unknown"
    published_date: Optional[str] = None
    modified_date: Optional[str] = None

    # Raw extracted elements (before normalization)
    raw_images: List[Dict[str, Any]] = field(default_factory=list)
    raw_links: List[Dict[str, Any]] = field(default_factory=list)
    featured_image_url: Optional[str] = None

    # SEO/metadata
    tags: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)


@dataclass
class FilmMenuItem:
    """Represents a film entry from the navigation menu."""
    film_title: str
    film_slug: str
    articles: List['ArticleMenuItem'] = field(default_factory=list)


@dataclass
class ArticleMenuItem:
    """Represents an article link from the navigation menu."""
    title: str
    url: str
    article_slug: str
