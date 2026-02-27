#!/usr/bin/env python3
"""
Command-line interface for the Deakins Forums scraper.

Usage:
    python -m deakins_forums.cli scrape-all
    python -m deakins_forums.cli scrape-forum team-deakins
    python -m deakins_forums.cli scrape-topic https://rogerdeakins.com/forums/topic/...
    python -m deakins_forums.cli build-index
    python -m deakins_forums.cli search "lighting techniques"
    python -m deakins_forums.cli stats
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

from .config import Settings
from .http_client import HttpClient
from .index_sqlite import SqliteIndex
from .pipeline import DeakinsPipeline
from .store_json import JsonLeafStore
from .export import TextExporter
from .coverage import CoverageTracker
from .report import print_coverage_report, print_quick_stats
from .query_tracker import QueryTracker
from .validate import validate_all_topics, validate_all_posts


def build_app(settings: Optional[Settings] = None):
    """Wire dependencies."""
    if settings is None:
        settings = Settings.from_env()

    store = JsonLeafStore(settings.out_dir)
    http = HttpClient(
        user_agent=settings.user_agent,
        delay_s=settings.delay_s,
        timeout_s=settings.timeout_s,
        state_path=settings.out_dir / "_site" / "http_state.json",
        max_retries=settings.max_retries,
    )
    pipeline = DeakinsPipeline(settings.base_url, settings.out_dir, http=http)
    index = SqliteIndex(settings.out_dir / "_site" / "kb.sqlite")

    return pipeline, store, index, settings


def cmd_scrape_all(args):
    """Scrape all forums from the forums index."""
    pipeline, store, index, settings = build_app()

    print("=" * 70)
    print("Deakins Forums - Scrape All")
    print("=" * 70)
    print(f"Output directory: {settings.out_dir}")
    print(f"Rate limit: {settings.delay_s}s between requests")
    print("=" * 70)

    stats = pipeline.scrape_all_forums(
        forums_index_url=settings.forums_index_url,
        max_forums=args.max_forums,
        max_topics_per_forum=args.max_topics
    )

    print("\n" + "=" * 70)
    print("Scraping Complete!")
    print("=" * 70)
    print(f"Forums scraped: {stats['forums_scraped']}/{stats['total_forums']}")
    print(f"Topics scraped: {stats['total_topics']}")
    print(f"Posts saved: {stats['posts']}")
    print("=" * 70)

    if args.build_index:
        print("\nBuilding search index...")
        index_stats = index.rebuild_from_json_leafs(settings.out_dir)
        print(f"✓ Indexed {index_stats['posts_indexed']} posts")


def cmd_scrape_forum(args):
    """Scrape a single forum by slug."""
    pipeline, store, index, settings = build_app()

    forum_url = f"{settings.base_url}/forums/forum/{args.forum_slug}/"

    # Initialize query tracking if metadata provided
    query_metadata = None
    query_tracker = None

    if hasattr(args, 'query_name') and args.query_name:
        query_tracker = QueryTracker(settings.out_dir)
        query_metadata = query_tracker.start_query(
            query_name=args.query_name,
            querier_role=args.querier_role or "Unknown",
            querier_department=args.querier_department or "Unknown",
            query_context=args.query_context or "General research",
            query_intent=args.query_intent or "Forum exploration",
            target_forums=[args.forum_slug]
        )

        print("=" * 70)
        print(f"Query: {query_metadata.query_name}")
        print(f"Querier: {query_metadata.querier.role} ({query_metadata.querier.department})")
        print(f"Context: {query_metadata.querier.context}")
        print(f"Intent: {query_metadata.intent}")
        print("=" * 70)

    print("=" * 70)
    print(f"Deakins Forums - Scrape Forum: {args.forum_slug}")
    print("=" * 70)

    # Track existing topics before scraping
    topics_before = set()
    topics_dir = settings.out_dir / "topics"
    if topics_dir.exists():
        topics_before = {
            f.stem for f in topics_dir.iterdir()
            if f.name.startswith(f"{args.forum_slug}__") and f.suffix == ".json"
        }

    forum_leaf = pipeline.scrape_forum(
        forum_url=forum_url,
        forum_slug=args.forum_slug,
        max_pages=args.max_pages,
        max_topics=args.max_topics
    )

    # Track which topics were accessed and which are new
    if query_tracker and query_metadata:
        topics_after = {
            f.stem for f in topics_dir.iterdir()
            if f.name.startswith(f"{args.forum_slug}__") and f.suffix == ".json"
        }

        newly_scraped = topics_after - topics_before
        revisited = topics_before & topics_after

        # Log all accessed topics
        for topic_file in topics_dir.iterdir():
            if topic_file.name.startswith(f"{args.forum_slug}__") and topic_file.suffix == ".json":
                topic_slug = topic_file.stem.replace(f"{args.forum_slug}__", "")
                was_new = topic_file.stem in newly_scraped
                query_tracker.log_topic_access(
                    query_metadata=query_metadata,
                    topic_slug=topic_slug,
                    forum_slug=args.forum_slug,
                    was_new_scrape=was_new
                )

        # Finalize query
        query_tracker.finalize_query(query_metadata)

        print(f"\n📊 Query Stats:")
        print(f"  Topics Accessed: {len(query_metadata.topics_accessed)}")
        print(f"  Newly Scraped: {len(query_metadata.topics_newly_scraped)}")
        print(f"  Revisited: {len(query_metadata.topics_revisited)}")

    print(f"\n✓ Complete: {len(forum_leaf.topic_refs)} topics")

    if args.build_index:
        print("\nBuilding search index...")
        index_stats = index.rebuild_from_json_leafs(settings.out_dir)
        print(f"✓ Indexed {index_stats['posts_indexed']} posts")


def cmd_scrape_topic(args):
    """Scrape a single topic by URL."""
    pipeline, store, index, settings = build_app()

    print("=" * 70)
    print(f"Deakins Forums - Scrape Topic")
    print("=" * 70)

    topic_leaf = pipeline.scrape_topic(
        topic_url=args.topic_url,
        max_pages=args.max_pages
    )

    print(f"\n✓ Complete: {len(topic_leaf.post_ids)} posts")

    if args.build_index:
        print("\nBuilding search index...")
        index_stats = index.rebuild_from_json_leafs(settings.out_dir)
        print(f"✓ Indexed {index_stats['posts_indexed']} posts")


def cmd_build_index(args):
    """Build or rebuild the search index."""
    pipeline, store, index, settings = build_app()

    use_curated = getattr(args, 'use_curated', False)

    print("=" * 70)
    print(f"Building Search Index{' (Curated Data)' if use_curated else ''}")
    print("=" * 70)

    if use_curated:
        print(f"Indexing from: {settings.out_dir / '_curated' / 'personas'}")
    else:
        print(f"Indexing from: {settings.out_dir / 'posts'}")

    stats = index.rebuild_from_json_leafs(settings.out_dir, use_curated=use_curated)

    print(f"✓ Indexed {stats['posts_indexed']} posts")
    print(f"Database: {settings.out_dir / '_site' / 'kb.sqlite'}")

    # Print curation stats if using curated data
    if use_curated:
        index_stats = index.get_stats()
        print("\nCuration Statistics:")
        print(f"  Cinematography posts: {index_stats.get('cinematography_posts', 0)}")
        print(f"  Housekeeping posts: {index_stats.get('housekeeping_posts', 0)}")

        if index_stats.get('persona_distribution'):
            print("\n  Persona Distribution:")
            for tier in ['S', 'A', 'B', 'C', 'D']:
                count = index_stats['persona_distribution'].get(tier, 0)
                if count > 0:
                    print(f"    {tier}-Tier: {count} posts")


def cmd_search(args):
    """Search the indexed posts."""
    pipeline, store, index, settings = build_app()

    # Build filter description
    filters = []
    if args.forum:
        filters.append(f"forum={args.forum}")
    if args.author:
        filters.append(f"author={args.author}")
    if getattr(args, 'persona', None):
        filters.append(f"persona={args.persona}")
    if getattr(args, 'cinematography_only', False):
        filters.append("cinematography-only")
    if getattr(args, 'exclude_housekeeping', False):
        filters.append("no-housekeeping")

    print("=" * 70)
    print(f"Search: {args.query}")
    if filters:
        print(f"Filters: {', '.join(filters)}")
    print("=" * 70)

    results = index.search_posts(
        query=args.query,
        forum_slug=args.forum,
        author=args.author,
        persona_tier=getattr(args, 'persona', None),
        cinematography_only=getattr(args, 'cinematography_only', False),
        exclude_housekeeping=getattr(args, 'exclude_housekeeping', False),
        limit=args.limit
    )

    if not results:
        print("No results found.")
        return

    for i, result in enumerate(results, 1):
        print(f"\n[{i}] Post #{result['post_id']}")
        print(f"    Author: {result['author']} ({result['author_role']})", end="")

        # Show persona tier if available
        if result.get('author_persona_tier'):
            tier_name = {
                'S': 'Master', 'A': 'Professional', 'B': 'Student',
                'C': 'Enthusiast', 'D': 'Visitor'
            }.get(result['author_persona_tier'], '')
            print(f" [{result['author_persona_tier']}-{tier_name}]")
        else:
            print()

        print(f"    Forum: {result['forum_slug']} / Topic: {result['topic_slug']}")
        if result['timestamp_iso']:
            print(f"    Date: {result['timestamp_iso']}")
        print(f"    URL: {result['reply_permalink'] or result['topic_url']}")

        # Show curation flags if present
        flags = []
        if result.get('is_housekeeping'):
            flags.append("housekeeping")
        if not result.get('filtered_from_cinematography'):
            flags.append("cinematography")
        if flags:
            print(f"    Tags: {', '.join(flags)}")

        print(f"    Snippet: {result['snippet']}")

    print(f"\n{len(results)} results")


def cmd_stats(args):
    """Show statistics about the scraped data."""
    pipeline, store, index, settings = build_app()

    print("=" * 70)
    print("Deakins Forums - Statistics")
    print("=" * 70)

    # Storage stats
    storage_stats = store.get_stats()
    print(f"\nStorage (JSON leafs):")
    print(f"  Posts:  {storage_stats['posts']}")
    print(f"  Topics: {storage_stats['topics']}")
    print(f"  Forums: {storage_stats['forums']}")

    # Index stats
    try:
        index_stats = index.get_stats()
        print(f"\nSearch Index:")
        print(f"  Indexed posts:  {index_stats['total_posts']}")
        print(f"  Forums:         {index_stats['total_forums']}")
        print(f"  Topics:         {index_stats['total_topics']}")
        print(f"  Authors:        {index_stats['total_authors']}")

        # Curation statistics (if available)
        if index_stats.get('persona_distribution'):
            print(f"\nCuration Metadata:")
            print(f"  Cinematography posts: {index_stats.get('cinematography_posts', 0)}")
            print(f"  Housekeeping posts:   {index_stats.get('housekeeping_posts', 0)}")

            print(f"\n  Persona Distribution:")
            tier_names = {
                'S': 'Master Cinematographers',
                'A': 'Working Professionals',
                'B': 'Serious Students & Emerging DPs',
                'C': 'Enthusiasts & Hobbyists',
                'D': 'One-Time Visitors'
            }
            for tier in ['S', 'A', 'B', 'C', 'D']:
                count = index_stats['persona_distribution'].get(tier, 0)
                if count > 0:
                    print(f"    {tier}-Tier ({tier_names[tier][:25]:25s}): {count:4d} posts")
    except Exception as e:
        print(f"\nSearch Index: Not built yet (run 'build-index')")

    # Check for curated data
    curated_dir = settings.out_dir / "_curated"
    if curated_dir.exists():
        print(f"\nCurated Data:")
        print(f"  Location: {curated_dir}")

        # Check for metadata file
        metadata_file = curated_dir / "metadata.json"
        if metadata_file.exists():
            import json
            with open(metadata_file) as f:
                metadata = json.load(f)

            stats = metadata.get('statistics', {})
            print(f"  Generated: {metadata.get('generated_at', 'Unknown')[:10]}")
            print(f"  Cinematography posts: {stats.get('cinematography_posts', 0)}")
            print(f"  Housekeeping filtered: {stats.get('housekeeping_filtered', 0)}")
            print(f"  High-engagement topics: {stats.get('high_engagement_topics', 0)}")
            print(f"  Consolidated buckets: {stats.get('consolidation_buckets', 0)}")
            print(f"  Topics consolidated: {stats.get('consolidated_topics', 0)}")

    print(f"\nOutput directory: {settings.out_dir}")


def cmd_export(args):
    """Export text data in various formats."""
    pipeline, store, index, settings = build_app()

    print("=" * 70)
    print(f"Exporting: {args.format}")
    print("=" * 70)

    exporter = TextExporter(settings.out_dir)
    output_path = Path(args.output)

    if args.format == "all-text":
        result = exporter.export_all_posts_text(output_path)
    elif args.format == "csv":
        result = exporter.export_posts_csv(output_path)
    elif args.format == "by-author":
        result = exporter.export_by_author(output_path)
    elif args.format == "by-topic":
        result = exporter.export_by_topic(output_path)
    elif args.format == "quotes":
        result = exporter.export_quotes_only(output_path)
    elif args.format == "links":
        result = exporter.export_links(output_path)
    elif args.format == "roger-only":
        result = exporter.export_roger_deakins_only(output_path)
    elif args.format == "blocks":
        result = exporter.export_content_blocks(output_path)
    elif args.format == "stats":
        result = exporter.export_statistics(output_path)

    print("\n✓ Export complete!")
    import json
    print(json.dumps(result, indent=2))


def cmd_coverage(args):
    """Show coverage report."""
    pipeline, store, index, settings = build_app()

    tracker = CoverageTracker(settings.out_dir)

    # Load previous coverage
    previous = tracker.load_previous_coverage()

    # Generate current report
    current = tracker.generate_report(settings.out_dir)

    # Calculate delta
    delta = tracker.calculate_delta(current) if previous else None

    # Save current coverage
    tracker.save_coverage(current)

    # Print report
    if args.format == "full":
        print_coverage_report(current, delta)
    elif args.format == "quick":
        print_quick_stats(current)
    else:
        print_coverage_report(current, delta)


def cmd_provenance(args):
    """Show query provenance report."""
    pipeline, store, index, settings = build_app()

    query_tracker = QueryTracker(settings.out_dir)

    if args.topic:
        # Show provenance for a specific topic
        forum_slug, topic_slug = args.topic.split("__", 1) if "__" in args.topic else (args.topic, None)
        if topic_slug:
            accesses = query_tracker.get_topic_provenance(topic_slug, forum_slug)
            print(f"\nProvenance for: {args.topic}")
            print("=" * 70)
            if accesses:
                for access in accesses:
                    print(f"  {access['timestamp'][:19]}")
                    print(f"    Query: {access['query_name']}")
                    print(f"    Querier: {access['querier_role']}")
                    print(f"    New Scrape: {access['was_new_scrape']}")
                    print()
            else:
                print("  No access records found for this topic.")
        else:
            print("Error: Invalid topic format. Use: forum__topic-slug")
    elif args.query_id:
        # Show specific query details
        query_data = query_tracker.get_query_summary(args.query_id)
        if query_data:
            import json
            print(json.dumps(query_data, indent=2))
        else:
            print(f"Query ID not found: {args.query_id}")
    else:
        # Show full provenance report
        report = query_tracker.generate_provenance_report()
        print(report)


def cmd_validate(args):
    """Validate data integrity."""
    pipeline, store, index, settings = build_app()

    print("=" * 70)
    print("Deakins Forums - Data Validation")
    print("=" * 70)

    # Validate topics
    print("\nValidating topics...")
    topic_results = validate_all_topics(store, verbose=args.verbose)

    print(f"  Topics checked: {topic_results['topics_checked']}")
    print(f"  Errors:   {topic_results['errors']}")
    print(f"  Warnings: {topic_results['warnings']}")
    print(f"  Info:     {topic_results['info']}")

    # Validate posts
    print("\nValidating posts...")
    post_results = validate_all_posts(store, verbose=args.verbose)

    print(f"  Posts checked: {post_results['posts_checked']}")
    print(f"  Errors:   {post_results['errors']}")
    print(f"  Warnings: {post_results['warnings']}")
    print(f"  Info:     {post_results['info']}")

    # Summary
    print("\n" + "=" * 70)
    total_errors = topic_results['errors'] + post_results['errors']
    total_warnings = topic_results['warnings'] + post_results['warnings']

    if total_errors == 0 and total_warnings == 0:
        print("✓ All validation checks passed!")
    elif total_errors == 0:
        print(f"⚠ Validation passed with {total_warnings} warnings")
    else:
        print(f"✗ Validation failed: {total_errors} errors, {total_warnings} warnings")

    print("=" * 70)

    # Exit code: 0 if no errors, 1 if errors found
    return 0 if total_errors == 0 else 1


def cmd_auth_setup(args):
    """Run Playwright to extract and save member session cookies."""
    from .auth_playwright import save_session_cookies
    print("=" * 70)
    print("Deakins Forums - Auth Setup")
    print("=" * 70)
    print("Extracting rogerdeakins.com session cookies via Playwright...")
    print("(Saved to session_cookies.json — gitignored, never committed)")
    print()
    save_session_cookies(project_root=Path("."))


def cmd_scrape_articles(args):
    """Scrape the Looking at Lighting article series."""
    cookies_path = Path("session_cookies.json")
    if not cookies_path.exists():
        print("ERROR: session_cookies.json not found.")
        print("  Run 'deakins-forums auth-setup' first to save your member session cookies.")
        return 1

    pipeline, store, index, settings = build_app()
    pipeline.http.load_cookies(cookies_path)

    print("=" * 70)
    print("Deakins Forums - Scrape Articles (Looking at Lighting)")
    print("=" * 70)
    print(f"Cookies: {cookies_path}")
    print(f"Output:  {settings.out_dir / 'posts'} (unified with forum posts)")
    print("=" * 70)

    stats = pipeline.scrape_lal_series()

    print("\n" + "=" * 70)
    print("Article Scrape Complete!")
    print("=" * 70)
    print(f"  Total URLs discovered: {stats['total']}")
    print(f"  Scraped (new/updated): {stats['scraped']}")
    print(f"  Not modified (cached): {stats['skipped_not_modified']}")
    print(f"  Restricted (auth):     {stats['restricted']}")
    print(f"  Errors:                {stats['errors']}")
    print("=" * 70)

    if stats["restricted"] > 0:
        print("\nWARNING: Some articles were restricted. Your session cookies may have expired.")
        print("  Re-run 'deakins-forums auth-setup' to refresh them.")

    if args.build_index:
        print("\nBuilding unified search index...")
        index_stats = index.rebuild_from_json_leafs(settings.out_dir)
        print(f"  ✓ Indexed {index_stats['posts_indexed']} items (forum posts + articles)")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Deakins Forums scraper and knowledge base builder"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # scrape-all command
    p_scrape_all = subparsers.add_parser("scrape-all", help="Scrape all forums")
    p_scrape_all.add_argument("--max-forums", type=int, help="Max forums to scrape (for testing)")
    p_scrape_all.add_argument("--max-topics", type=int, default=1000, help="Max topics per forum")
    p_scrape_all.add_argument("--build-index", action="store_true", help="Build index after scraping")

    # scrape-forum command
    p_scrape_forum = subparsers.add_parser("scrape-forum", help="Scrape a single forum")
    p_scrape_forum.add_argument("forum_slug", help="Forum slug (e.g., 'team-deakins')")
    p_scrape_forum.add_argument("--max-pages", type=int, default=20, help="Max forum pages")
    p_scrape_forum.add_argument("--max-topics", type=int, default=1000, help="Max topics to scrape")
    p_scrape_forum.add_argument("--build-index", action="store_true", help="Build index after scraping")
    # Query tracking parameters
    p_scrape_forum.add_argument("--query-name", help="Name of the research query")
    p_scrape_forum.add_argument("--querier-role", help="Role of the person making the query (e.g., 'Director', 'DP')")
    p_scrape_forum.add_argument("--querier-department", help="Department (e.g., 'Camera', 'Lighting', 'Production')")
    p_scrape_forum.add_argument("--query-context", help="Context of the query (e.g., 'TV miniseries development')")
    p_scrape_forum.add_argument("--query-intent", help="Research objective/question")

    # scrape-topic command
    p_scrape_topic = subparsers.add_parser("scrape-topic", help="Scrape a single topic")
    p_scrape_topic.add_argument("topic_url", help="Full topic URL")
    p_scrape_topic.add_argument("--max-pages", type=int, default=50, help="Max topic pages")
    p_scrape_topic.add_argument("--build-index", action="store_true", help="Build index after scraping")

    # build-index command
    p_build_index = subparsers.add_parser("build-index", help="Build search index")
    p_build_index.add_argument("--use-curated", action="store_true", help="Index from curated persona data instead of original posts")

    # search command
    p_search = subparsers.add_parser("search", help="Search indexed posts")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument("--forum", help="Filter by forum slug")
    p_search.add_argument("--author", help="Filter by author name")
    p_search.add_argument("--persona", choices=['S', 'A', 'B', 'C', 'D'], help="Filter by persona tier (S=Master, A=Professional, B=Student, C=Enthusiast, D=Visitor)")
    p_search.add_argument("--cinematography-only", action="store_true", help="Only include pure cinematography posts (exclude housekeeping)")
    p_search.add_argument("--exclude-housekeeping", action="store_true", help="Exclude housekeeping posts")
    p_search.add_argument("--limit", type=int, default=20, help="Max results")

    # stats command
    p_stats = subparsers.add_parser("stats", help="Show statistics")

    # export command
    p_export = subparsers.add_parser("export", help="Export text data")
    p_export.add_argument("format", choices=[
        "all-text", "csv", "by-author", "by-topic",
        "quotes", "links", "roger-only", "blocks", "stats"
    ], help="Export format")
    p_export.add_argument("--output", "-o", required=True, help="Output file or directory")

    # coverage command
    p_coverage = subparsers.add_parser("coverage", help="Show coverage report")
    p_coverage.add_argument("--format", choices=["full", "quick"], default="full", help="Report format")

    # provenance command
    p_provenance = subparsers.add_parser("provenance", help="Show query provenance/lineage report")
    p_provenance.add_argument("--topic", help="Show provenance for specific topic (format: forum__topic-slug)")
    p_provenance.add_argument("--query-id", help="Show details for specific query ID")

    # validate command
    p_validate = subparsers.add_parser("validate", help="Validate data integrity")
    p_validate.add_argument("--verbose", "-v", action="store_true", help="Print all validation errors")

    # auth-setup command
    subparsers.add_parser("auth-setup", help="Save browser session cookies for member-only content (requires playwright)")

    # scrape-articles command
    p_scrape_articles = subparsers.add_parser("scrape-articles", help="Scrape Looking at Lighting articles (requires auth-setup first)")
    p_scrape_articles.add_argument("--build-index", action="store_true", help="Rebuild unified search index after scraping")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        if args.command == "scrape-all":
            cmd_scrape_all(args)
        elif args.command == "scrape-forum":
            cmd_scrape_forum(args)
        elif args.command == "scrape-topic":
            cmd_scrape_topic(args)
        elif args.command == "build-index":
            cmd_build_index(args)
        elif args.command == "search":
            cmd_search(args)
        elif args.command == "stats":
            cmd_stats(args)
        elif args.command == "export":
            cmd_export(args)
        elif args.command == "coverage":
            cmd_coverage(args)
        elif args.command == "provenance":
            cmd_provenance(args)
        elif args.command == "validate":
            return cmd_validate(args)
        elif args.command == "auth-setup":
            cmd_auth_setup(args)
        elif args.command == "scrape-articles":
            return cmd_scrape_articles(args) or 0
        else:
            parser.print_help()
            return 1

        return 0

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
