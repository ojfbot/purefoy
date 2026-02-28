#!/usr/bin/env python3
"""
Text extraction and export utilities for forum data.

Extracts raw text content from JSON leafs for analysis.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .store_json import JsonLeafStore


class TextExporter:
    """Extract and export text content from forum data."""

    def __init__(self, out_dir: Path):
        self.store = JsonLeafStore(out_dir)

    def export_all_posts_text(self, output_file: Path) -> dict[str, int]:
        """
        Export all post text to a single text file.

        Returns statistics about exported content.
        """
        posts = self.store.list_all_posts()

        with open(output_file, 'w', encoding='utf-8') as f:
            for post in posts:
                f.write("=" * 80 + "\n")
                f.write(f"POST ID: {post.ids.post_id}\n")
                f.write(f"AUTHOR: {post.author.display_name if post.author else 'Unknown'}\n")
                f.write(f"ROLE: {post.author.role if post.author else 'N/A'}\n")
                f.write(f"FORUM: {post.ids.forum_slug or 'N/A'}\n")
                f.write(f"TOPIC: {post.ids.topic_slug or 'N/A'}\n")
                f.write(f"TIMESTAMP: {post.timestamps.parsed_iso or post.timestamps.raw or 'N/A'}\n")
                f.write("=" * 80 + "\n")
                f.write(post.content_text)
                f.write("\n\n")

        return {
            "total_posts": len(posts),
            "output_file": str(output_file)
        }

    def export_posts_csv(self, output_file: Path) -> dict[str, int]:
        """
        Export posts to CSV format for analysis.

        Includes: post_id, author, role, forum, topic, timestamp, content_text, url
        """
        posts = self.store.list_all_posts()

        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'post_id', 'author', 'role', 'forum_slug', 'topic_slug',
                'timestamp_iso', 'timestamp_raw', 'content_text',
                'num_quotes', 'num_links', 'num_media', 'source_url'
            ])

            for post in posts:
                writer.writerow([
                    post.ids.post_id,
                    post.author.display_name if post.author else '',
                    post.author.role if post.author else '',
                    post.ids.forum_slug or '',
                    post.ids.topic_slug or '',
                    post.timestamps.parsed_iso or '',
                    post.timestamps.raw or '',
                    post.content_text,
                    len(post.quotes),
                    len(post.links),
                    len(post.media),
                    post.provenance.source_url
                ])

        return {
            "total_posts": len(posts),
            "output_file": str(output_file)
        }

    def export_by_author(self, output_dir: Path) -> dict[str, Any]:
        """
        Export posts grouped by author into separate text files.

        Creates one file per author with all their posts.
        """
        posts = self.store.list_all_posts()
        output_dir.mkdir(parents=True, exist_ok=True)

        # Group by author
        by_author: dict[str, list] = {}
        for post in posts:
            author = post.author.display_name if post.author else "Unknown"
            if author not in by_author:
                by_author[author] = []
            by_author[author].append(post)

        # Write one file per author
        for author, author_posts in by_author.items():
            # Sanitize filename
            safe_author = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in author)
            filename = output_dir / f"{safe_author}.txt"

            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"AUTHOR: {author}\n")
                f.write(f"TOTAL POSTS: {len(author_posts)}\n")
                f.write("=" * 80 + "\n\n")

                for post in author_posts:
                    f.write(f"POST ID: {post.ids.post_id}\n")
                    f.write(f"TOPIC: {post.ids.topic_slug or 'N/A'}\n")
                    f.write(f"TIMESTAMP: {post.timestamps.parsed_iso or post.timestamps.raw or 'N/A'}\n")
                    f.write("-" * 80 + "\n")
                    f.write(post.content_text)
                    f.write("\n\n" + "=" * 80 + "\n\n")

        return {
            "total_authors": len(by_author),
            "total_posts": len(posts),
            "output_dir": str(output_dir)
        }

    def export_by_topic(self, output_dir: Path) -> dict[str, Any]:
        """
        Export posts grouped by topic into separate text files.

        Creates one file per topic with all its posts in order.
        """
        topics = self.store.list_all_topics()
        output_dir.mkdir(parents=True, exist_ok=True)

        total_posts = 0

        for topic in topics:
            # Sanitize filename
            topic_name = topic.topic_slug or "unknown"
            safe_topic = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in topic_name)
            filename = output_dir / f"{safe_topic}.txt"

            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"TOPIC: {topic.title or topic.topic_slug}\n")
                f.write(f"FORUM: {topic.forum_slug or 'N/A'}\n")
                f.write(f"URL: {topic.topic_url}\n")
                f.write(f"TOTAL POSTS: {len(topic.post_ids)}\n")
                f.write("=" * 80 + "\n\n")

                # Load and write each post
                for post_id in topic.post_ids:
                    post = self.store.read_post(post_id)
                    if post:
                        total_posts += 1
                        f.write(f"POST ID: {post.ids.post_id}\n")
                        f.write(f"AUTHOR: {post.author.display_name if post.author else 'Unknown'}")
                        if post.author and post.author.role:
                            f.write(f" ({post.author.role})")
                        f.write("\n")
                        f.write(f"TIMESTAMP: {post.timestamps.parsed_iso or post.timestamps.raw or 'N/A'}\n")
                        f.write("-" * 80 + "\n")
                        f.write(post.content_text)
                        f.write("\n\n" + "=" * 80 + "\n\n")

        return {
            "total_topics": len(topics),
            "total_posts": total_posts,
            "output_dir": str(output_dir)
        }

    def export_quotes_only(self, output_file: Path) -> dict[str, int]:
        """
        Export all extracted quotes with attribution.
        """
        posts = self.store.list_all_posts()

        total_quotes = 0
        with open(output_file, 'w', encoding='utf-8') as f:
            for post in posts:
                if post.quotes:
                    for quote in post.quotes:
                        total_quotes += 1
                        f.write("=" * 80 + "\n")
                        f.write(f"FROM POST: {post.ids.post_id}\n")
                        f.write(f"AUTHOR: {post.author.display_name if post.author else 'Unknown'}\n")
                        if quote.attributed_to:
                            f.write(f"ATTRIBUTED TO: {quote.attributed_to}\n")
                        f.write("-" * 80 + "\n")
                        f.write(quote.text)
                        f.write("\n\n")

        return {
            "total_quotes": total_quotes,
            "total_posts_with_quotes": sum(1 for p in posts if p.quotes),
            "output_file": str(output_file)
        }

    def export_links(self, output_file: Path) -> dict[str, int]:
        """
        Export all extracted links to CSV.
        """
        posts = self.store.list_all_posts()

        total_links = 0
        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['post_id', 'author', 'link_href', 'link_text', 'link_kind'])

            for post in posts:
                for link in post.links:
                    total_links += 1
                    writer.writerow([
                        post.ids.post_id,
                        post.author.display_name if post.author else '',
                        link.href,
                        link.text or '',
                        link.kind
                    ])

        return {
            "total_links": total_links,
            "output_file": str(output_file)
        }

    def export_roger_deakins_only(self, output_file: Path) -> dict[str, int]:
        """
        Export only posts by Roger Deakins.
        """
        posts = self.store.list_all_posts()
        roger_posts = [
            p for p in posts
            if p.author and p.author.role and 'Roger Deakins' in p.author.role
        ]

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("ROGER DEAKINS POSTS\n")
            f.write("=" * 80 + "\n\n")

            for post in roger_posts:
                f.write(f"POST ID: {post.ids.post_id}\n")
                f.write(f"TOPIC: {post.ids.topic_slug or 'N/A'}\n")
                f.write(f"FORUM: {post.ids.forum_slug or 'N/A'}\n")
                f.write(f"TIMESTAMP: {post.timestamps.parsed_iso or post.timestamps.raw or 'N/A'}\n")
                f.write(f"URL: {post.provenance.source_url}\n")
                f.write("=" * 80 + "\n")
                f.write(post.content_text)
                f.write("\n\n" + "=" * 80 + "\n\n")

        return {
            "roger_posts": len(roger_posts),
            "total_posts": len(posts),
            "output_file": str(output_file)
        }

    def export_content_blocks(self, output_file: Path) -> dict[str, int]:
        """
        Export structured content blocks (paragraphs, quotes, lists, code).
        """
        posts = self.store.list_all_posts()

        with open(output_file, 'w', encoding='utf-8') as f:
            for post in posts:
                if post.blocks:
                    f.write("=" * 80 + "\n")
                    f.write(f"POST ID: {post.ids.post_id}\n")
                    f.write(f"AUTHOR: {post.author.display_name if post.author else 'Unknown'}\n")
                    f.write("=" * 80 + "\n\n")

                    for i, block in enumerate(post.blocks, 1):
                        f.write(f"[{block.type.upper()} {i}]\n")
                        f.write("-" * 40 + "\n")
                        f.write(block.text)
                        f.write("\n\n")

                    f.write("\n")

        return {
            "total_posts_with_blocks": sum(1 for p in posts if p.blocks),
            "total_blocks": sum(len(p.blocks) for p in posts),
            "output_file": str(output_file)
        }

    def export_statistics(self, output_file: Path) -> dict[str, Any]:
        """
        Export comprehensive statistics about the corpus.
        """
        posts = self.store.list_all_posts()
        topics = self.store.list_all_topics()
        forums = self.store.list_all_forums()

        # Gather stats
        authors = set()
        forum_slugs = set()
        topic_slugs = set()
        total_text_length = 0
        total_quotes = 0
        total_links = 0
        total_media = 0
        total_blocks = 0

        posts_by_author: dict[str, int] = {}

        for post in posts:
            if post.author:
                authors.add(post.author.display_name)
                posts_by_author[post.author.display_name] = posts_by_author.get(post.author.display_name, 0) + 1

            if post.ids.forum_slug:
                forum_slugs.add(post.ids.forum_slug)
            if post.ids.topic_slug:
                topic_slugs.add(post.ids.topic_slug)

            total_text_length += len(post.content_text)
            total_quotes += len(post.quotes)
            total_links += len(post.links)
            total_media += len(post.media)
            total_blocks += len(post.blocks)

        stats = {
            "corpus_statistics": {
                "total_posts": len(posts),
                "total_topics": len(topics),
                "total_forums": len(forums),
                "unique_authors": len(authors),
                "unique_forum_slugs": len(forum_slugs),
                "unique_topic_slugs": len(topic_slugs),
                "total_text_length": total_text_length,
                "average_post_length": total_text_length // len(posts) if posts else 0,
                "total_quotes": total_quotes,
                "total_links": total_links,
                "total_media": total_media,
                "total_content_blocks": total_blocks
            },
            "top_authors": sorted(posts_by_author.items(), key=lambda x: x[1], reverse=True)[:20],
            "authors_list": sorted(list(authors)),
            "forums_list": sorted(list(forum_slugs)),
            "topics_list": sorted(list(topic_slugs))
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)

        return stats


def main():
    """CLI for text export utilities."""
    import argparse

    from .config import Settings

    parser = argparse.ArgumentParser(description="Export forum text data")
    parser.add_argument("command", choices=[
        "all-text", "csv", "by-author", "by-topic",
        "quotes", "links", "roger-only", "blocks", "stats"
    ])
    parser.add_argument("--output", "-o", required=True, help="Output file or directory")

    args = parser.parse_args()
    settings = Settings.from_env()
    exporter = TextExporter(settings.out_dir)

    output_path = Path(args.output)

    print(f"Exporting {args.command}...")

    if args.command == "all-text":
        result = exporter.export_all_posts_text(output_path)
    elif args.command == "csv":
        result = exporter.export_posts_csv(output_path)
    elif args.command == "by-author":
        result = exporter.export_by_author(output_path)
    elif args.command == "by-topic":
        result = exporter.export_by_topic(output_path)
    elif args.command == "quotes":
        result = exporter.export_quotes_only(output_path)
    elif args.command == "links":
        result = exporter.export_links(output_path)
    elif args.command == "roger-only":
        result = exporter.export_roger_deakins_only(output_path)
    elif args.command == "blocks":
        result = exporter.export_content_blocks(output_path)
    elif args.command == "stats":
        result = exporter.export_statistics(output_path)
    else:
        print("Unknown command")
        return 1

    print("✓ Export complete!")
    print(json.dumps(result, indent=2))

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
