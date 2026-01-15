"""
Data models for the Deakins Forums knowledge base.

These models are designed to be:
1) Ultra-structured for downstream agent use (search, summarization, citation)
2) Stable on disk as JSON "leafs" (posts, topics, forums)
3) Incrementally updatable (content_hash + provenance)
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional, Union
from pydantic import BaseModel, Field


class PostType(str, Enum):
    """Distinguish topic starters from replies."""
    TOPIC = "topic"      # Original post that starts a thread
    REPLY = "reply"      # Response to a topic or another reply


class HttpProvenance(BaseModel):
    """HTTP-level provenance for a fetched page or extracted entity."""
    url: str
    status: Optional[int] = None
    etag: Optional[str] = None
    last_modified: Optional[str] = None


class Provenance(BaseModel):
    """Provenance metadata used for auditability and incremental refresh."""
    source_url: str
    scraped_at: str
    http: Optional[HttpProvenance] = None


class Link(BaseModel):
    """A hyperlink extracted from post content."""
    href: str
    text: Optional[str] = None
    kind: Literal["internal", "external"]


class Media(BaseModel):
    """Media reference extracted from a post (images first; extend for attachments later)."""
    src: str
    alt: Optional[str] = None
    kind: Literal["image", "attachment"] = "image"


class Quote(BaseModel):
    """A quoted block, optionally attributed (best-effort)."""
    text: str
    attributed_to: Optional[str] = None


class ContentBlock(BaseModel):
    """A structured content block for agent-friendly reconstruction."""
    type: Literal["paragraph", "quote", "list", "code", "heading", "unknown"] = "unknown"
    text: str


class PostIds(BaseModel):
    """Identifiers that allow stable joins across leafs and threading."""
    post_id: str
    forum_slug: Optional[str] = None
    topic_slug: Optional[str] = None
    reply_permalink: Optional[str] = None

    # NEW: Parent relationship for reply threading
    parent_post_id: Optional[str] = None  # ID of post this replies to (None for topic starters)
    parent_type: Optional[PostType] = None  # Whether parent is topic or reply

    # NEW: Position tracking for chronological ordering
    position: Optional[int] = None  # Reply position within thread (0 for topic, 1+ for replies)


class Author(BaseModel):
    """Represents a forum author as displayed on the site."""
    display_name: str
    role: Optional[str] = None  # Participant / Keymaster / etc


class Timestamps(BaseModel):
    """Captures raw timestamp plus parsed version when possible."""
    raw: Optional[str] = None
    parsed_iso: Optional[str] = None
    parse_confidence: Literal["high", "medium", "low", "none"] = "none"


class Integrity(BaseModel):
    """Integrity metadata for incremental update detection."""
    content_hash: str
    parser_version: str = "bbpress-v1"


class PostLeaf(BaseModel):
    """A single post leaf JSON file with full threading context."""
    ids: PostIds

    # NEW: Explicit post type classification
    post_type: PostType = PostType.TOPIC  # Default to TOPIC for backward compatibility

    author: Optional[Author] = None
    timestamps: Timestamps = Field(default_factory=Timestamps)
    content_text: str
    content_html: Optional[str] = None
    blocks: list[ContentBlock] = Field(default_factory=list)
    quotes: list[Quote] = Field(default_factory=list)
    links: list[Link] = Field(default_factory=list)
    media: list[Media] = Field(default_factory=list)
    provenance: Provenance
    integrity: Integrity


class TopicLeaf(BaseModel):
    """Topic metadata + post index with structured reply tree."""
    topic_url: str
    forum_slug: Optional[str] = None
    topic_slug: Optional[str] = None
    title: Optional[str] = None
    breadcrumb: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    # Flat list of all post IDs (maintains backward compatibility)
    post_ids: list[str] = Field(default_factory=list)

    # NEW: Structured reply tree for agent-friendly traversal
    reply_tree: Optional[dict[str, Any]] = None
    # Format: {"post_id": "12345", "author": "...", "children": [{"post_id": "12346", ...}]}

    # NEW: Quick statistics
    reply_count: int = 0  # Total number of replies (excludes topic starter)
    max_depth: int = 0    # Maximum thread nesting depth

    provenance: Provenance
    integrity: Integrity


class ForumLeaf(BaseModel):
    """Forum metadata + topic index."""
    forum_url: str
    forum_slug: str
    title: str
    description: Optional[str] = None
    subforums: list[dict[str, Any]] = Field(default_factory=list)
    topic_refs: list[dict[str, Any]] = Field(default_factory=list)
    provenance: Provenance
    integrity: Integrity
