"""
Migration utilities for upgrading scraped data to new schema versions.

Usage:
    python -m deakins_forums.migrate --rebuild-trees
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import Settings
from .models import PostType, Integrity
from .store_json import JsonLeafStore
from .reply_tree import build_reply_tree, calculate_thread_stats


def migrate_v1_to_v2(store: JsonLeafStore, dry_run: bool = False) -> dict:
    """
    Migrate from bbpress-v1 to bbpress-v2 schema.

    Changes in v2:
    - PostLeaf: Added post_type, parent_post_id, parent_type, position fields
    - TopicLeaf: Added reply_tree, reply_count, max_depth fields
    - parser_version updated to "bbpress-v2"

    For existing data scraped with v1:
    - Posts already have parent fields (may be None for old data)
    - This migration rebuilds reply trees and statistics for all topics

    Parameters
    ----------
    store:
        Store to migrate
    dry_run:
        If True, show what would be done without modifying files

    Returns
    -------
    Migration statistics
    """
    print("=" * 70)
    print("Migration: bbpress-v1 → bbpress-v2")
    print("=" * 70)

    stats = {
        "topics_processed": 0,
        "topics_updated": 0,
        "topics_skipped": 0,
        "posts_checked": 0,
        "posts_with_parents": 0,
        "errors": 0,
    }

    # Load all topics
    topics = store.list_all_topics()
    print(f"\nFound {len(topics)} topics to migrate\n")

    for i, topic in enumerate(topics, 1):
        print(f"[{i}/{len(topics)}] {topic.topic_slug or 'unknown'}")
        stats["topics_processed"] += 1

        try:
            # Check if already migrated (has reply_tree)
            if topic.reply_tree is not None and topic.provenance.http:
                print(f"  ✓ Already has reply tree, skipping")
                stats["topics_skipped"] += 1
                continue

            # Load posts to check if they have parent fields
            posts_have_parents = False
            for post_id in topic.post_ids[:5]:  # Check first 5
                post = store.read_post(post_id)
                if post:
                    stats["posts_checked"] += 1
                    if hasattr(post.ids, 'parent_post_id') and post.ids.parent_post_id:
                        posts_have_parents = True
                        stats["posts_with_parents"] += 1

            if not posts_have_parents:
                print(f"  ⚠ Posts don't have parent fields - need to re-scrape topic")
                stats["topics_skipped"] += 1
                continue

            # Build reply tree
            reply_tree = build_reply_tree(topic.post_ids, store)
            if not reply_tree:
                print(f"  ✗ Failed to build reply tree (no root post found)")
                stats["errors"] += 1
                continue

            # Calculate statistics
            thread_stats = calculate_thread_stats(reply_tree)

            # Update topic
            topic.reply_tree = reply_tree
            topic.reply_count = thread_stats["reply_count"]
            topic.max_depth = thread_stats["max_depth"]
            topic.integrity.parser_version = "bbpress-v2"

            if not dry_run:
                store.write_topic(topic)
                print(f"  ✓ Updated: {thread_stats['reply_count']} replies, depth {thread_stats['max_depth']}")
            else:
                print(f"  [DRY RUN] Would update: {thread_stats['reply_count']} replies, depth {thread_stats['max_depth']}")

            stats["topics_updated"] += 1

        except Exception as e:
            print(f"  ✗ Error: {e}")
            stats["errors"] += 1
            continue

    # Summary
    print("\n" + "=" * 70)
    print("Migration Summary")
    print("=" * 70)
    print(f"Topics processed: {stats['topics_processed']}")
    print(f"Topics updated:   {stats['topics_updated']}")
    print(f"Topics skipped:   {stats['topics_skipped']}")
    print(f"Posts checked:    {stats['posts_checked']}")
    print(f"Posts w/parents:  {stats['posts_with_parents']}")
    print(f"Errors:           {stats['errors']}")
    print("=" * 70)

    if dry_run:
        print("\nDRY RUN - No files were modified")

    return stats


def rebuild_all_reply_trees(store: JsonLeafStore, dry_run: bool = False) -> dict:
    """
    Force rebuild reply trees for all topics.

    Useful if:
    - Reply tree building logic has changed
    - Data integrity issues detected
    - Want to regenerate trees from updated posts

    Parameters
    ----------
    store:
        Store to rebuild
    dry_run:
        If True, show what would be done without modifying files

    Returns
    -------
    Rebuild statistics
    """
    print("=" * 70)
    print("Rebuild Reply Trees")
    print("=" * 70)

    stats = {
        "topics_processed": 0,
        "topics_rebuilt": 0,
        "errors": 0,
    }

    topics = store.list_all_topics()
    print(f"\nRebuilding {len(topics)} topics\n")

    for i, topic in enumerate(topics, 1):
        print(f"[{i}/{len(topics)}] {topic.topic_slug or 'unknown'}")
        stats["topics_processed"] += 1

        try:
            # Always rebuild
            reply_tree = build_reply_tree(topic.post_ids, store)
            if not reply_tree:
                print(f"  ✗ Failed to build reply tree")
                stats["errors"] += 1
                continue

            # Calculate statistics
            thread_stats = calculate_thread_stats(reply_tree)

            # Update topic
            topic.reply_tree = reply_tree
            topic.reply_count = thread_stats["reply_count"]
            topic.max_depth = thread_stats["max_depth"]

            if not dry_run:
                store.write_topic(topic)
                print(f"  ✓ Rebuilt: {thread_stats['reply_count']} replies, depth {thread_stats['max_depth']}")
            else:
                print(f"  [DRY RUN] Would rebuild: {thread_stats['reply_count']} replies, depth {thread_stats['max_depth']}")

            stats["topics_rebuilt"] += 1

        except Exception as e:
            print(f"  ✗ Error: {e}")
            stats["errors"] += 1
            continue

    # Summary
    print("\n" + "=" * 70)
    print("Rebuild Summary")
    print("=" * 70)
    print(f"Topics processed: {stats['topics_processed']}")
    print(f"Topics rebuilt:   {stats['topics_rebuilt']}")
    print(f"Errors:           {stats['errors']}")
    print("=" * 70)

    if dry_run:
        print("\nDRY RUN - No files were modified")

    return stats


def main():
    """CLI entry point for migrations."""
    parser = argparse.ArgumentParser(
        description="Migrate Deakins Forums data to new schema versions"
    )

    parser.add_argument(
        "--rebuild-trees",
        action="store_true",
        help="Rebuild all reply trees (force regeneration)"
    )
    parser.add_argument(
        "--migrate-v2",
        action="store_true",
        help="Migrate from v1 to v2 schema (adds reply trees)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        help="Output directory (default: from config)"
    )

    args = parser.parse_args()

    # Load settings
    settings = Settings.from_env()
    if args.out_dir:
        settings.out_dir = args.out_dir

    store = JsonLeafStore(settings.out_dir)

    try:
        if args.rebuild_trees:
            stats = rebuild_all_reply_trees(store, dry_run=args.dry_run)
            return 0 if stats["errors"] == 0 else 1

        elif args.migrate_v2:
            stats = migrate_v1_to_v2(store, dry_run=args.dry_run)
            return 0 if stats["errors"] == 0 else 1

        else:
            parser.print_help()
            return 1

    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        return 130

    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
