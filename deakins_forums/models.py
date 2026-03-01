"""
Data models for the Deakins Forums knowledge base.

These models are designed to be:
1) Ultra-structured for downstream agent use (search, summarization, citation)
2) Stable on disk as JSON "leafs" (posts, topics, forums)
3) Incrementally updatable (content_hash + provenance)
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class PostType(StrEnum):
    """Distinguish topic starters from replies."""

    TOPIC = "topic"  # Original post that starts a thread
    REPLY = "reply"  # Response to a topic or another reply
    ARTICLE = "article"  # Blog/LAL article (rogerdeakins.com)


class HttpProvenance(BaseModel):
    """HTTP-level provenance for a fetched page or extracted entity."""

    url: str
    status: int | None = None
    etag: str | None = None
    last_modified: str | None = None


class Provenance(BaseModel):
    """Provenance metadata used for auditability and incremental refresh."""

    source_url: str
    scraped_at: str
    http: HttpProvenance | None = None


class Link(BaseModel):
    """A hyperlink extracted from post content."""

    href: str
    text: str | None = None
    kind: Literal["internal", "external"]


class Media(BaseModel):
    """Media reference extracted from a post (images first; extend for attachments later)."""

    src: str
    alt: str | None = None
    kind: Literal["image", "attachment"] = "image"
    local_path: str | None = None  # Relative path within library/forums/ (gitignored)


class Quote(BaseModel):
    """A quoted block, optionally attributed (best-effort)."""

    text: str
    attributed_to: str | None = None


class ContentBlock(BaseModel):
    """A structured content block for agent-friendly reconstruction."""

    type: Literal["paragraph", "quote", "list", "code", "heading", "unknown"] = "unknown"
    text: str


class PostIds(BaseModel):
    """Identifiers that allow stable joins across leafs and threading."""

    post_id: str
    forum_slug: str | None = None
    topic_slug: str | None = None
    reply_permalink: str | None = None

    # Parent relationship for reply threading
    parent_post_id: str | None = None  # ID of post this replies to (None for topic starters)
    parent_type: PostType | None = None  # Whether parent is topic or reply

    # Position tracking for chronological ordering
    position: int | None = None  # Reply position within thread (0 for topic, 1+ for replies)

    # WordPress post ID (articles only)
    wp_post_id: str | None = None


class Author(BaseModel):
    """Represents a forum author as displayed on the site."""

    display_name: str
    role: str | None = None  # Participant / Keymaster / etc


class Timestamps(BaseModel):
    """Captures raw timestamp plus parsed version when possible."""

    raw: str | None = None
    parsed_iso: str | None = None
    parse_confidence: Literal["high", "medium", "low", "none"] = "none"


class Integrity(BaseModel):
    """Integrity metadata for incremental update detection."""

    content_hash: str
    parser_version: str = "bbpress-v1"


class PostLeaf(BaseModel):
    """A single post leaf JSON file with full threading context."""

    ids: PostIds

    # Explicit post type classification
    post_type: PostType = PostType.TOPIC  # Default to TOPIC for backward compatibility

    author: Author | None = None
    timestamps: Timestamps = Field(default_factory=Timestamps)
    content_text: str
    content_html: str | None = None
    blocks: list[ContentBlock] = Field(default_factory=list)
    quotes: list[Quote] = Field(default_factory=list)
    links: list[Link] = Field(default_factory=list)
    media: list[Media] = Field(default_factory=list)

    # Article-only fields (None for forum posts)
    title: str | None = None  # Article title
    description: str | None = None  # Meta description / excerpt
    featured_image: str | None = None  # Featured image URL
    series: str | None = None  # Series slug, e.g. "lal"

    provenance: Provenance
    integrity: Integrity


class TopicLeaf(BaseModel):
    """Topic metadata + post index with structured reply tree."""

    topic_url: str
    forum_slug: str | None = None
    topic_slug: str | None = None
    title: str | None = None
    breadcrumb: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    # Flat list of all post IDs (maintains backward compatibility)
    post_ids: list[str] = Field(default_factory=list)

    # Structured reply tree for agent-friendly traversal
    reply_tree: Any | None = None
    # Format: {"post_id": "12345", "author": "...", "children": [{"post_id": "12346", ...}]}

    # Quick statistics
    reply_count: int = 0  # Total number of replies (excludes topic starter)
    max_depth: int = 0  # Maximum thread nesting depth

    provenance: Provenance
    integrity: Integrity


class ForumLeaf(BaseModel):
    """Forum metadata + topic index."""

    forum_url: str
    forum_slug: str
    title: str
    description: str | None = None
    subforums: list[Any] = Field(default_factory=list)
    topic_refs: list[Any] = Field(default_factory=list)
    provenance: Provenance
    integrity: Integrity
