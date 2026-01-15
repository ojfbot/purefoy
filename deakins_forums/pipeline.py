"""
High-level scraping pipeline.

This module glues together:
- HttpClient (fetch)
- parser_bbpress (extract)
- normalize (ultra-structure)
- store_json (persist leafs)

It is designed to be called from:
- a CLI
- an MCP tool
- a scheduled job
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin, urlparse
import re

from dateutil import parser as dtparser

from .http_client import HttpClient
from .models import (
    Author,
    ForumLeaf,
    HttpProvenance,
    Integrity,
    PostIds,
    PostLeaf,
    PostType,
    Provenance,
    Timestamps,
    TopicLeaf,
)
from .parser_bbpress import (
    parse_forums_index,
    parse_forum_page,
    parse_topic_page,
    find_next_page_url,
)
from .store_json import JsonLeafStore
from .normalize import extract_links_media_quotes_blocks
from .reply_tree import build_reply_tree, calculate_thread_stats


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="ignore")).hexdigest()


def _parse_timestamp(raw: Optional[str]) -> tuple[Optional[str], str]:
    """
    Parse the forum timestamp string into ISO 8601 when possible.

    Returns
    -------
    parsed_iso:
        ISO 8601 string if parse succeeded (timezone may be naive if not present).
    confidence:
        'high' if fully parsed, else 'medium', 'low', or 'none'
    """
    if not raw:
        return None, "none"
    # raw examples look like "January 18, 2023 at 3:32 pm #175763"
    cleaned = raw.split("#", 1)[0].strip()
    try:
        dt = dtparser.parse(cleaned, fuzzy=True)
        return dt.isoformat(), "medium"
    except Exception:
        return None, "low"


def _extract_slug_from_url(url: str, pattern: str) -> Optional[str]:
    """Extract slug from URL using regex pattern."""
    m = re.search(pattern, url)
    return m.group(1) if m else None


class DeakinsPipeline:
    """
    Composable pipeline for building a local forum knowledge base.

    Design goals:
    - deterministic leaf file paths
    - incremental refresh (HttpClient conditional GET + content_hash)
    - clean substeps that can be reused by agents
    """

    def __init__(self, base_url: str, out_dir: Path, http: HttpClient) -> None:
        self.base_url = base_url.rstrip("/")
        self.store = JsonLeafStore(out_dir)
        self.http = http

    def scrape_forums_index(self, forums_url: str) -> list[dict]:
        """Fetch /forums/ and persist a minimal forums index manifest."""
        print(f"Scraping forums index: {forums_url}")
        res = self.http.fetch(forums_url)
        if res.not_modified:
            print("  ✓ Not modified (using cached)")
            return self.store.read_forums_index() or []

        assert res.text is not None
        refs = parse_forums_index(self.base_url, res.text)
        payload = [{"url": r.url, "slug": r.slug, "title": r.title} for r in refs]
        self.store.write_forums_index(payload, content_hash=_sha256(res.text))
        print(f"  ✓ Found {len(refs)} forums")
        return payload

    def scrape_topic(
        self,
        topic_url: str,
        forum_slug: Optional[str] = None,
        topic_slug: Optional[str] = None,
        max_pages: int = 50
    ) -> TopicLeaf:
        """
        Scrape all pages of a single topic.

        Parameters
        ----------
        topic_url:
            The starting URL of the topic
        forum_slug:
            Optional forum slug for organization
        topic_slug:
            Optional topic slug (extracted from URL if not provided)
        max_pages:
            Maximum pages to scrape (safety limit)

        Returns
        -------
        TopicLeaf with all post IDs from all pages
        """
        # Extract topic slug from URL if not provided
        if not topic_slug:
            topic_slug = _extract_slug_from_url(topic_url, r"/forums/topic/([^/]+)")

        print(f"Scraping topic: {topic_url}")

        all_posts_ids: list[str] = []
        current_url = topic_url
        page_num = 1
        title = None

        while current_url and page_num <= max_pages:
            if page_num > 1:
                print(f"  → Page {page_num}")

            res = self.http.fetch(current_url)
            if res.not_modified:
                print(f"  ✓ Page {page_num} not modified")
                # Try to load existing topic
                existing = self.store.read_topic_by_url(topic_url)
                if existing:
                    return existing
                break

            assert res.text is not None
            page_title, raw_posts, pagination = parse_topic_page(self.base_url, res.text)

            if not title:
                title = page_title

            print(f"  ✓ Page {page_num}: Found {len(raw_posts)} posts")

            # Process each post
            for rp in raw_posts:
                parsed_iso, conf = _parse_timestamp(rp.timestamp_raw)
                blocks, quotes, links, media = extract_links_media_quotes_blocks(
                    self.base_url, rp.content_text, rp.content_html
                )

                # Convert string post_type to enum
                post_type_enum = PostType.TOPIC if rp.post_type == "topic" else PostType.REPLY

                # Convert string parent_type to enum if present
                parent_type_enum = None
                if rp.parent_type:
                    parent_type_enum = PostType.TOPIC if rp.parent_type == "topic" else PostType.REPLY

                post_leaf = PostLeaf(
                    ids=PostIds(
                        post_id=rp.post_id,
                        forum_slug=forum_slug,
                        topic_slug=topic_slug,
                        reply_permalink=rp.reply_permalink,
                        parent_post_id=rp.parent_post_id,
                        parent_type=parent_type_enum,
                        position=rp.position,
                    ),
                    post_type=post_type_enum,
                    author=Author(display_name=rp.author or "unknown", role=rp.role),
                    timestamps=Timestamps(
                        raw=rp.timestamp_raw,
                        parsed_iso=parsed_iso,
                        parse_confidence=conf
                    ),
                    content_text=rp.content_text,
                    content_html=rp.content_html,
                    blocks=blocks,
                    quotes=quotes,
                    links=links,
                    media=media,
                    provenance=Provenance(
                        source_url=current_url,
                        scraped_at=self.store.now_iso(),
                        http=HttpProvenance(
                            url=current_url,
                            status=res.status,
                            etag=res.etag,
                            last_modified=res.last_modified
                        ),
                    ),
                    integrity=Integrity(
                        content_hash=_sha256(rp.content_text + (rp.content_html or "")),
                        parser_version="bbpress-v2"  # Increment version for new schema
                    ),
                )
                self.store.write_post(post_leaf)
                all_posts_ids.append(rp.post_id)

            # Find next page
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(res.text, "html.parser")
            next_url = find_next_page_url(self.base_url, soup, current_url)

            if not next_url or (pagination and not pagination.has_next):
                break

            current_url = next_url
            page_num += 1

        # Build reply tree from collected posts
        print("  Building reply tree...")
        reply_tree = build_reply_tree(all_posts_ids, self.store)

        # Calculate thread statistics
        stats = calculate_thread_stats(reply_tree)

        # Create topic leaf
        topic_leaf = TopicLeaf(
            topic_url=topic_url,
            forum_slug=forum_slug,
            topic_slug=topic_slug,
            title=title,
            post_ids=all_posts_ids,
            reply_tree=reply_tree,
            reply_count=stats["reply_count"],
            max_depth=stats["max_depth"],
            provenance=Provenance(
                source_url=topic_url,
                scraped_at=self.store.now_iso(),
                http=HttpProvenance(url=topic_url, status=200, etag=None, last_modified=None),
            ),
            integrity=Integrity(
                content_hash=_sha256(topic_url + str(all_posts_ids)),
                parser_version="bbpress-v2"
            ),
        )
        self.store.write_topic(topic_leaf)
        print(f"  ✓ Topic complete: {len(all_posts_ids)} total posts, {stats['reply_count']} replies, max depth {stats['max_depth']}, across {page_num} pages")

        return topic_leaf

    def scrape_forum(
        self,
        forum_url: str,
        forum_slug: Optional[str] = None,
        max_pages: int = 20,
        max_topics: int = 1000
    ) -> ForumLeaf:
        """
        Scrape a forum: all its pages, all topics on those pages.

        Parameters
        ----------
        forum_url:
            The forum URL (e.g., https://rogerdeakins.com/forums/forum/team-deakins/)
        forum_slug:
            Optional forum slug (extracted from URL if not provided)
        max_pages:
            Maximum forum pages to scrape
        max_topics:
            Maximum topics to scrape from this forum

        Returns
        -------
        ForumLeaf with metadata and topic references
        """
        # Extract forum slug from URL if not provided
        if not forum_slug:
            forum_slug = _extract_slug_from_url(forum_url, r"/forums/forum/([^/]+)")

        if not forum_slug:
            raise ValueError(f"Could not extract forum slug from URL: {forum_url}")

        print(f"\n{'='*70}")
        print(f"Scraping forum: {forum_url}")
        print(f"{'='*70}")

        current_url = forum_url
        page_num = 1
        all_subforums: list[dict] = []
        all_topics: list[dict] = []
        forum_title = ""
        forum_description = None

        while current_url and page_num <= max_pages and len(all_topics) < max_topics:
            if page_num > 1:
                print(f"\n--- Forum page {page_num} ---")

            res = self.http.fetch(current_url)
            if res.not_modified:
                print(f"  ✓ Page {page_num} not modified")
                existing = self.store.read_forum(forum_slug)
                if existing:
                    return existing
                break

            assert res.text is not None
            subforums, topics, pagination = parse_forum_page(self.base_url, forum_slug, res.text)

            # Extract title from first page
            if page_num == 1:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(res.text, "html.parser")
                h = soup.find(["h1", "h2"])
                if h:
                    forum_title = h.get_text(strip=True)

                # Store subforums
                all_subforums = [
                    {"url": sf.url, "slug": sf.slug, "title": sf.title}
                    for sf in subforums
                ]

            print(f"  ✓ Page {page_num}: Found {len(topics)} topics")

            # Add topics to collection
            for topic in topics:
                if len(all_topics) >= max_topics:
                    break
                all_topics.append({
                    "url": topic.url,
                    "slug": topic.slug,
                    "title": topic.title,
                    "started_by": topic.started_by
                })

            # Find next page
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(res.text, "html.parser")
            next_url = find_next_page_url(self.base_url, soup, current_url)

            if not next_url or (pagination and not pagination.has_next):
                break

            current_url = next_url
            page_num += 1

        print(f"\n  ✓ Forum index complete: {len(all_topics)} topics, {len(all_subforums)} subforums")

        # Now scrape each topic
        print(f"\n  Scraping {len(all_topics)} topics...")
        topics_scraped = 0
        for i, topic_info in enumerate(all_topics, 1):
            print(f"\n  [{i}/{len(all_topics)}] {topic_info['title']}")
            try:
                self.scrape_topic(
                    topic_url=topic_info["url"],
                    forum_slug=forum_slug,
                    topic_slug=topic_info["slug"]
                )
                topics_scraped += 1
            except Exception as e:
                print(f"    ✗ Error scraping topic: {e}")

        # Create forum leaf
        forum_leaf = ForumLeaf(
            forum_url=forum_url,
            forum_slug=forum_slug,
            title=forum_title or forum_slug,
            description=forum_description,
            subforums=all_subforums,
            topic_refs=all_topics,
            provenance=Provenance(
                source_url=forum_url,
                scraped_at=self.store.now_iso(),
                http=HttpProvenance(url=forum_url, status=200, etag=None, last_modified=None),
            ),
            integrity=Integrity(content_hash=_sha256(forum_url + str(all_topics))),
        )
        self.store.write_forum(forum_leaf)

        print(f"\n{'='*70}")
        print(f"✓ Forum complete: {topics_scraped}/{len(all_topics)} topics scraped")
        print(f"{'='*70}\n")

        return forum_leaf

    def scrape_all_forums(
        self,
        forums_index_url: str,
        max_forums: Optional[int] = None,
        max_topics_per_forum: int = 1000
    ) -> dict[str, Any]:
        """
        Scrape all forums from the forums index.

        Parameters
        ----------
        forums_index_url:
            The main /forums/ URL
        max_forums:
            Limit number of forums to scrape (for testing)
        max_topics_per_forum:
            Max topics to scrape per forum

        Returns
        -------
        Summary statistics
        """
        # Get forum list
        forums_list = self.scrape_forums_index(forums_index_url)

        if max_forums:
            forums_list = forums_list[:max_forums]

        print(f"\nWill scrape {len(forums_list)} forums")

        forums_scraped = 0
        total_topics = 0

        for i, forum_info in enumerate(forums_list, 1):
            print(f"\n[{i}/{len(forums_list)}] Forum: {forum_info['title']}")
            try:
                forum_leaf = self.scrape_forum(
                    forum_url=forum_info["url"],
                    forum_slug=forum_info["slug"],
                    max_topics=max_topics_per_forum
                )
                forums_scraped += 1
                total_topics += len(forum_leaf.topic_refs)
            except Exception as e:
                print(f"  ✗ Error scraping forum: {e}")

        stats = self.store.get_stats()
        return {
            "forums_scraped": forums_scraped,
            "total_forums": len(forums_list),
            "total_topics": total_topics,
            **stats
        }
