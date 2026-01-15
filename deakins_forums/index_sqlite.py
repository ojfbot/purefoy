"""
SQLite FTS5 index for full-text search across forum posts.

Provides fast search with snippet extraction and relevance ranking.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Optional

from .store_json import JsonLeafStore


class SqliteIndex:
    """
    Full-text search index for forum posts using SQLite FTS5.

    Schema:
    - posts_fts: FTS5 virtual table with post_id, author, forum_slug, topic_slug, content_text
    - posts_meta: Metadata table with timestamps, URLs, etc.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        """Initialize the database schema."""
        # FTS5 virtual table for full-text search
        self.conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS posts_fts USING fts5(
                post_id UNINDEXED,
                author,
                forum_slug,
                topic_slug,
                content_text,
                tokenize = 'porter unicode61'
            )
        """)

        # Metadata table for additional post information
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS posts_meta (
                post_id TEXT PRIMARY KEY,
                author TEXT,
                author_role TEXT,
                forum_slug TEXT,
                topic_slug TEXT,
                timestamp_raw TEXT,
                timestamp_iso TEXT,
                reply_permalink TEXT,
                topic_url TEXT,
                scraped_at TEXT,
                content_hash TEXT
            )
        """)

        # Index for efficient filtering
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_forum_slug ON posts_meta(forum_slug)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_author ON posts_meta(author)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_topic_slug ON posts_meta(topic_slug)")

        self.conn.commit()

    def index_post(self, post_data: dict[str, Any]) -> None:
        """Index a single post."""
        ids = post_data.get("ids", {})
        author = post_data.get("author", {})
        timestamps = post_data.get("timestamps", {})
        provenance = post_data.get("provenance", {})
        integrity = post_data.get("integrity", {})

        post_id = ids.get("post_id")
        if not post_id:
            return

        # Insert into FTS table
        self.conn.execute("""
            INSERT OR REPLACE INTO posts_fts (post_id, author, forum_slug, topic_slug, content_text)
            VALUES (?, ?, ?, ?, ?)
        """, (
            post_id,
            author.get("display_name"),
            ids.get("forum_slug"),
            ids.get("topic_slug"),
            post_data.get("content_text", "")
        ))

        # Insert into metadata table
        self.conn.execute("""
            INSERT OR REPLACE INTO posts_meta (
                post_id, author, author_role, forum_slug, topic_slug,
                timestamp_raw, timestamp_iso, reply_permalink, topic_url,
                scraped_at, content_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            post_id,
            author.get("display_name"),
            author.get("role"),
            ids.get("forum_slug"),
            ids.get("topic_slug"),
            timestamps.get("raw"),
            timestamps.get("parsed_iso"),
            ids.get("reply_permalink"),
            provenance.get("source_url"),
            provenance.get("scraped_at"),
            integrity.get("content_hash")
        ))

        self.conn.commit()

    def search_posts(
        self,
        query: str,
        forum_slug: Optional[str] = None,
        author: Optional[str] = None,
        limit: int = 20
    ) -> list[dict[str, Any]]:
        """
        Search posts with optional filters.

        Returns results with snippets and relevance ranking.
        """
        # Build WHERE clauses
        where_clauses = []
        params = [query]

        if forum_slug:
            where_clauses.append("m.forum_slug = ?")
            params.append(forum_slug)

        if author:
            where_clauses.append("m.author LIKE ?")
            params.append(f"%{author}%")

        where_sql = " AND " + " AND ".join(where_clauses) if where_clauses else ""

        # Search with snippet extraction
        sql = f"""
            SELECT
                m.post_id,
                m.author,
                m.author_role,
                m.forum_slug,
                m.topic_slug,
                m.timestamp_iso,
                m.reply_permalink,
                m.topic_url,
                snippet(posts_fts, 4, '<mark>', '</mark>', '...', 32) as snippet,
                rank
            FROM posts_fts
            JOIN posts_meta m ON posts_fts.post_id = m.post_id
            WHERE posts_fts MATCH ?{where_sql}
            ORDER BY rank
            LIMIT ?
        """

        params.append(limit)

        cursor = self.conn.execute(sql, params)
        results = []

        for row in cursor:
            results.append({
                "post_id": row["post_id"],
                "author": row["author"],
                "author_role": row["author_role"],
                "forum_slug": row["forum_slug"],
                "topic_slug": row["topic_slug"],
                "timestamp_iso": row["timestamp_iso"],
                "reply_permalink": row["reply_permalink"],
                "topic_url": row["topic_url"],
                "snippet": row["snippet"],
                "rank": row["rank"]
            })

        return results

    def rebuild_from_json_leafs(self, out_dir: Path) -> dict[str, int]:
        """
        Rebuild the entire index from JSON leaf files.

        Returns statistics about indexed content.
        """
        store = JsonLeafStore(out_dir)

        # Clear existing index
        self.conn.execute("DELETE FROM posts_fts")
        self.conn.execute("DELETE FROM posts_meta")
        self.conn.commit()

        # Index all posts
        posts = store.list_all_posts()
        indexed_count = 0

        for post in posts:
            self.index_post(post.model_dump())
            indexed_count += 1

        self.conn.commit()

        return {
            "posts_indexed": indexed_count,
            "total_posts": len(posts)
        }

    def get_stats(self) -> dict[str, Any]:
        """Get index statistics."""
        cursor = self.conn.execute("SELECT COUNT(*) as count FROM posts_meta")
        total_posts = cursor.fetchone()["count"]

        cursor = self.conn.execute("SELECT COUNT(DISTINCT forum_slug) as count FROM posts_meta WHERE forum_slug IS NOT NULL")
        total_forums = cursor.fetchone()["count"]

        cursor = self.conn.execute("SELECT COUNT(DISTINCT author) as count FROM posts_meta WHERE author IS NOT NULL")
        total_authors = cursor.fetchone()["count"]

        cursor = self.conn.execute("SELECT COUNT(DISTINCT topic_slug) as count FROM posts_meta WHERE topic_slug IS NOT NULL")
        total_topics = cursor.fetchone()["count"]

        return {
            "total_posts": total_posts,
            "total_forums": total_forums,
            "total_topics": total_topics,
            "total_authors": total_authors
        }

    def close(self) -> None:
        """Close the database connection."""
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
