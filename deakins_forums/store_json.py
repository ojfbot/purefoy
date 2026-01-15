"""
JSON leaf store for posts, topics, and forums.

Each entity is stored as a separate JSON file:
- posts/<post_id>.json
- topics/<topic_slug>.json
- forums/<forum_slug>.json
- _site/forums_index.json (main forum list)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .models import ForumLeaf, PostLeaf, TopicLeaf


class JsonLeafStore:
    """
    File-based JSON storage for forum entities.

    Directory structure:
    ```
    out_dir/
      posts/
        <post_id>.json
      topics/
        <forum_slug>__<topic_slug>.json
      forums/
        <forum_slug>.json
      _site/
        forums_index.json
        http_state.json
    ```
    """

    def __init__(self, out_dir: Path) -> None:
        self.out_dir = out_dir
        self.posts_dir = out_dir / "posts"
        self.topics_dir = out_dir / "topics"
        self.forums_dir = out_dir / "forums"
        self.site_dir = out_dir / "_site"

        # Ensure directories exist
        self.posts_dir.mkdir(parents=True, exist_ok=True)
        self.topics_dir.mkdir(parents=True, exist_ok=True)
        self.forums_dir.mkdir(parents=True, exist_ok=True)
        self.site_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def now_iso() -> str:
        """Return current timestamp in ISO 8601 format."""
        return datetime.now(timezone.utc).isoformat()

    def write_post(self, post: PostLeaf) -> Path:
        """Write a post leaf to disk."""
        filepath = self.posts_dir / f"{post.ids.post_id}.json"
        filepath.write_text(
            post.model_dump_json(indent=2, exclude_none=True),
            encoding="utf-8"
        )
        return filepath

    def read_post(self, post_id: str) -> Optional[PostLeaf]:
        """Read a post leaf from disk."""
        filepath = self.posts_dir / f"{post_id}.json"
        if not filepath.exists():
            return None
        data = json.loads(filepath.read_text(encoding="utf-8"))
        return PostLeaf(**data)

    def write_topic(self, topic: TopicLeaf) -> Path:
        """Write a topic leaf to disk."""
        # Construct filename: forum__topic or just topic
        if topic.forum_slug and topic.topic_slug:
            filename = f"{topic.forum_slug}__{topic.topic_slug}.json"
        elif topic.topic_slug:
            filename = f"{topic.topic_slug}.json"
        else:
            # Fallback: use hash of URL
            import hashlib
            url_hash = hashlib.md5(topic.topic_url.encode()).hexdigest()[:12]
            filename = f"topic_{url_hash}.json"

        filepath = self.topics_dir / filename
        filepath.write_text(
            topic.model_dump_json(indent=2, exclude_none=True),
            encoding="utf-8"
        )
        return filepath

    def read_topic(self, forum_slug: str, topic_slug: str) -> Optional[TopicLeaf]:
        """Read a topic leaf by forum and topic slugs."""
        filename = f"{forum_slug}__{topic_slug}.json"
        filepath = self.topics_dir / filename
        if not filepath.exists():
            return None
        data = json.loads(filepath.read_text(encoding="utf-8"))
        return TopicLeaf(**data)

    def read_topic_by_url(self, topic_url: str) -> Optional[TopicLeaf]:
        """Read a topic by searching for matching URL."""
        for filepath in self.topics_dir.glob("*.json"):
            data = json.loads(filepath.read_text(encoding="utf-8"))
            if data.get("topic_url") == topic_url:
                return TopicLeaf(**data)
        return None

    def write_forum(self, forum: ForumLeaf) -> Path:
        """Write a forum leaf to disk."""
        filepath = self.forums_dir / f"{forum.forum_slug}.json"
        filepath.write_text(
            forum.model_dump_json(indent=2, exclude_none=True),
            encoding="utf-8"
        )
        return filepath

    def read_forum(self, forum_slug: str) -> Optional[ForumLeaf]:
        """Read a forum leaf from disk."""
        filepath = self.forums_dir / f"{forum_slug}.json"
        if not filepath.exists():
            return None
        data = json.loads(filepath.read_text(encoding="utf-8"))
        return ForumLeaf(**data)

    def write_forums_index(self, forums: list[dict[str, Any]], content_hash: str) -> Path:
        """Write the main forums index."""
        filepath = self.site_dir / "forums_index.json"
        payload = {
            "scraped_at": self.now_iso(),
            "content_hash": content_hash,
            "forums": forums
        }
        filepath.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return filepath

    def read_forums_index(self) -> Optional[list[dict[str, Any]]]:
        """Read the forums index."""
        filepath = self.site_dir / "forums_index.json"
        if not filepath.exists():
            return None
        data = json.loads(filepath.read_text(encoding="utf-8"))
        return data.get("forums", [])

    def list_all_posts(self) -> list[PostLeaf]:
        """List all post leafs."""
        posts = []
        for filepath in self.posts_dir.glob("*.json"):
            data = json.loads(filepath.read_text(encoding="utf-8"))
            posts.append(PostLeaf(**data))
        return posts

    def list_all_topics(self) -> list[TopicLeaf]:
        """List all topic leafs."""
        topics = []
        for filepath in self.topics_dir.glob("*.json"):
            data = json.loads(filepath.read_text(encoding="utf-8"))
            topics.append(TopicLeaf(**data))
        return topics

    def list_all_forums(self) -> list[ForumLeaf]:
        """List all forum leafs."""
        forums = []
        for filepath in self.forums_dir.glob("*.json"):
            data = json.loads(filepath.read_text(encoding="utf-8"))
            forums.append(ForumLeaf(**data))
        return forums

    def get_stats(self) -> dict[str, int]:
        """Get storage statistics."""
        return {
            "posts": len(list(self.posts_dir.glob("*.json"))),
            "topics": len(list(self.topics_dir.glob("*.json"))),
            "forums": len(list(self.forums_dir.glob("*.json"))),
        }
