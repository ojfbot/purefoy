"""
SQLite FTS5 index for full-text search across forum posts.

Provides fast search with snippet extraction and relevance ranking.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

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
                content_hash TEXT,
                is_housekeeping INTEGER DEFAULT 0,
                filtered_from_cinematography INTEGER DEFAULT 0,
                author_persona_tier TEXT,
                author_persona_score INTEGER,
                curated_at TEXT
            )
        """)

        # Index for efficient filtering
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_forum_slug ON posts_meta(forum_slug)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_author ON posts_meta(author)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_topic_slug ON posts_meta(topic_slug)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_persona_tier ON posts_meta(author_persona_tier)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_housekeeping ON posts_meta(is_housekeeping)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_cinematography ON posts_meta(filtered_from_cinematography)")

        # Safe migration: add content_type column if it doesn't exist yet
        try:
            self.conn.execute("ALTER TABLE posts_meta ADD COLUMN content_type TEXT DEFAULT 'post'")
        except Exception:
            pass  # Column already exists

        self.conn.commit()

    def index_post(self, post_data: dict[str, Any]) -> None:
        """Index a single post (forum post or article — post_type differentiates)."""
        ids = post_data.get("ids", {})
        author = post_data.get("author") or {}
        timestamps = post_data.get("timestamps", {})
        provenance = post_data.get("provenance", {})
        integrity = post_data.get("integrity", {})
        curation = post_data.get("curation", {})

        post_id = ids.get("post_id")
        if not post_id:
            return

        post_type = post_data.get("post_type", "topic")
        content_type = "article" if post_type == "article" else "post"

        # For articles: prepend title + description into searchable text
        content_text = post_data.get("content_text", "")
        if content_type == "article":
            title = post_data.get("title", "")
            description = post_data.get("description") or ""
            content_text = f"{title}\n{description}\n{content_text}".strip()

        # Insert into FTS table
        self.conn.execute("""
            INSERT OR REPLACE INTO posts_fts (post_id, author, forum_slug, topic_slug, content_text)
            VALUES (?, ?, ?, ?, ?)
        """, (
            post_id,
            author.get("display_name"),
            ids.get("forum_slug"),
            ids.get("topic_slug"),
            content_text,
        ))

        # Insert into metadata table
        self.conn.execute("""
            INSERT OR REPLACE INTO posts_meta (
                post_id, author, author_role, forum_slug, topic_slug,
                timestamp_raw, timestamp_iso, reply_permalink, topic_url,
                scraped_at, content_hash, content_type,
                is_housekeeping, filtered_from_cinematography,
                author_persona_tier, author_persona_score, curated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            integrity.get("content_hash"),
            content_type,
            1 if curation.get("is_housekeeping") else 0,
            1 if curation.get("filtered_from_cinematography") else 0,
            curation.get("author_persona_tier"),
            curation.get("author_persona_score"),
            curation.get("curated_at"),
        ))

        self.conn.commit()

    def search_posts(
        self,
        query: str,
        forum_slug: str | None = None,
        author: str | None = None,
        persona_tier: str | None = None,
        cinematography_only: bool = False,
        exclude_housekeeping: bool = False,
        limit: int = 20
    ) -> list[dict[str, Any]]:
        """
        Search posts with optional filters.

        Args:
            query: Search query string
            forum_slug: Filter by forum (e.g., "team-deakins")
            author: Filter by author name (partial match)
            persona_tier: Filter by persona tier (S, A, B, C, D)
            cinematography_only: Only include non-housekeeping cinematography posts
            exclude_housekeeping: Exclude housekeeping posts (regardless of cinematography filter)
            limit: Maximum number of results to return

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

        if persona_tier:
            where_clauses.append("m.author_persona_tier = ?")
            params.append(persona_tier)

        if cinematography_only:
            where_clauses.append("m.filtered_from_cinematography = 0")

        if exclude_housekeeping:
            where_clauses.append("m.is_housekeeping = 0")

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
                m.is_housekeeping,
                m.filtered_from_cinematography,
                m.author_persona_tier,
                m.author_persona_score,
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
                "is_housekeeping": bool(row["is_housekeeping"]),
                "filtered_from_cinematography": bool(row["filtered_from_cinematography"]),
                "author_persona_tier": row["author_persona_tier"],
                "author_persona_score": row["author_persona_score"],
                "snippet": row["snippet"],
                "rank": row["rank"]
            })

        return results

    def rebuild_from_json_leafs(self, out_dir: Path, use_curated: bool = False) -> dict[str, int]:
        """
        Rebuild the entire index from JSON leaf files.

        Args:
            out_dir: Base directory containing forum data
            use_curated: If True, index from _curated/personas/* subdirectories instead of posts/

        Returns statistics about indexed content.
        """
        # Clear existing index
        self.conn.execute("DELETE FROM posts_fts")
        self.conn.execute("DELETE FROM posts_meta")
        self.conn.commit()

        indexed_count = 0

        if use_curated:
            # Index from curated persona directories
            curated_dir = out_dir / "_curated" / "personas"

            for tier_dir in curated_dir.iterdir():
                if not tier_dir.is_dir():
                    continue

                posts_dir = tier_dir / "posts"
                if not posts_dir.exists():
                    continue

                for post_file in posts_dir.glob("*.json"):
                    try:
                        import json
                        with open(post_file) as f:
                            post_data = json.load(f)
                        self.index_post(post_data)
                        indexed_count += 1
                    except Exception:
                        continue
        else:
            # Index from original posts directory
            store = JsonLeafStore(out_dir)
            posts = store.list_all_posts()

            for post in posts:
                self.index_post(post.model_dump())
                indexed_count += 1

        self.conn.commit()

        return {
            "posts_indexed": indexed_count,
            "use_curated": use_curated,
        }

    def get_stats(self) -> dict[str, Any]:
        """Get index statistics including curation metadata."""
        cursor = self.conn.execute("SELECT COUNT(*) as count FROM posts_meta")
        total_posts = cursor.fetchone()["count"]

        cursor = self.conn.execute("SELECT COUNT(DISTINCT forum_slug) as count FROM posts_meta WHERE forum_slug IS NOT NULL")
        total_forums = cursor.fetchone()["count"]

        cursor = self.conn.execute("SELECT COUNT(DISTINCT author) as count FROM posts_meta WHERE author IS NOT NULL")
        total_authors = cursor.fetchone()["count"]

        cursor = self.conn.execute("SELECT COUNT(DISTINCT topic_slug) as count FROM posts_meta WHERE topic_slug IS NOT NULL")
        total_topics = cursor.fetchone()["count"]

        # Curation statistics
        cursor = self.conn.execute("SELECT COUNT(*) as count FROM posts_meta WHERE is_housekeeping = 1")
        housekeeping_posts = cursor.fetchone()["count"]

        cursor = self.conn.execute("SELECT COUNT(*) as count FROM posts_meta WHERE filtered_from_cinematography = 0")
        cinematography_posts = cursor.fetchone()["count"]

        # Persona distribution
        cursor = self.conn.execute("""
            SELECT author_persona_tier, COUNT(*) as count
            FROM posts_meta
            WHERE author_persona_tier IS NOT NULL
            GROUP BY author_persona_tier
            ORDER BY author_persona_tier
        """)
        persona_distribution = {row["author_persona_tier"]: row["count"] for row in cursor}

        return {
            "total_posts": total_posts,
            "total_forums": total_forums,
            "total_topics": total_topics,
            "total_authors": total_authors,
            "housekeeping_posts": housekeeping_posts,
            "cinematography_posts": cinematography_posts,
            "persona_distribution": persona_distribution
        }

    def get_posts_by_persona(self, tier: str, limit: int = 100) -> list[dict[str, Any]]:
        """
        Get posts by persona tier.

        Args:
            tier: Persona tier (S, A, B, C, D)
            limit: Maximum number of posts to return

        Returns list of post metadata.
        """
        sql = """
            SELECT
                post_id, author, author_role, forum_slug, topic_slug,
                timestamp_iso, reply_permalink, topic_url,
                author_persona_tier, author_persona_score
            FROM posts_meta
            WHERE author_persona_tier = ?
            ORDER BY timestamp_iso DESC
            LIMIT ?
        """

        cursor = self.conn.execute(sql, (tier, limit))
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
                "author_persona_tier": row["author_persona_tier"],
                "author_persona_score": row["author_persona_score"]
            })

        return results

    def get_cinematography_posts(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        Get non-housekeeping cinematography posts.

        Args:
            limit: Maximum number of posts to return

        Returns list of post metadata.
        """
        sql = """
            SELECT
                post_id, author, author_role, forum_slug, topic_slug,
                timestamp_iso, reply_permalink, topic_url,
                author_persona_tier, author_persona_score
            FROM posts_meta
            WHERE filtered_from_cinematography = 0 AND is_housekeeping = 0
            ORDER BY timestamp_iso DESC
            LIMIT ?
        """

        cursor = self.conn.execute(sql, (limit,))
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
                "author_persona_tier": row["author_persona_tier"],
                "author_persona_score": row["author_persona_score"]
            })

        return results

    def close(self) -> None:
        """Close the database connection."""
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
