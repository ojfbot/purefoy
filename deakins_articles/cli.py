"""
Command-line interface for articles scraper.
"""

import argparse
import sys
from pathlib import Path

from .config import load_settings
from .pipeline import build_pipeline
from .store import ArticleJsonStore


def cmd_scrape_all(args):
    """Scrape all articles from all films."""
    settings = load_settings(
        override_username=args.username,
        override_password=args.password,
    )

    # Validate settings
    errors = settings.validate()
    if errors:
        print("Configuration errors:")
        for error in errors:
            print(f"  - {error}")
        return 1

    # Build pipeline
    try:
        pipeline = build_pipeline(settings)
    except Exception as e:
        print(f"✗ Failed to initialize: {e}")
        return 1

    # Scrape
    try:
        index = pipeline.scrape_all_articles(
            max_films=args.max_films,
            max_articles_per_film=args.max_articles,
        )

        if index:
            print(f"\n✓ Articles index saved to: {settings.out_dir / '_site' / 'articles_index.json'}")
            return 0
        else:
            print("\n✗ Scraping failed")
            return 1

    except Exception as e:
        print(f"\n✗ Error during scraping: {e}")
        import traceback
        traceback.print_exc()
        return 1


def cmd_scrape_film(args):
    """Scrape all articles for a specific film."""
    settings = load_settings(
        override_username=args.username,
        override_password=args.password,
    )

    # Build pipeline
    try:
        pipeline = build_pipeline(settings)
    except Exception as e:
        print(f"✗ Failed to initialize: {e}")
        return 1

    # Discover films
    films_data = pipeline.scrape_articles_menu()

    # Find matching film
    film_data = None
    for film in films_data:
        if film["film_slug"] == args.film_slug:
            film_data = film
            break

    if not film_data:
        print(f"✗ Film not found: {args.film_slug}")
        print(f"\nAvailable films:")
        for film in films_data:
            print(f"  - {film['film_slug']} ({len(film['articles'])} articles)")
        return 1

    # Scrape film
    try:
        film_section = pipeline.scrape_film(
            film_slug=film_data["film_slug"],
            film_title=film_data["film_title"],
            articles=film_data["articles"],
            max_articles=args.max_articles,
        )

        if film_section:
            print(f"\n✓ Film data saved to: {settings.out_dir / 'films' / f'{args.film_slug}.json'}")
            return 0
        else:
            return 1

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


def cmd_scrape_article(args):
    """Scrape a single article."""
    settings = load_settings(
        override_username=args.username,
        override_password=args.password,
    )

    # Build pipeline
    try:
        pipeline = build_pipeline(settings)
    except Exception as e:
        print(f"✗ Failed to initialize: {e}")
        return 1

    # Scrape article
    try:
        article = pipeline.scrape_article(
            article_url=args.url,
            film_slug=args.film_slug,
            skip_if_exists=not args.force,
        )

        if article:
            print(f"\n✓ Article saved to: {settings.out_dir / 'articles' / f'{article.ids.article_id}.json'}")
            return 0
        else:
            return 1

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


def cmd_list_films(args):
    """List all discovered films and articles."""
    settings = load_settings(
        override_username=args.username,
        override_password=args.password,
    )

    # Build pipeline
    try:
        pipeline = build_pipeline(settings)
    except Exception as e:
        print(f"✗ Failed to initialize: {e}")
        return 1

    # Discover films
    films_data = pipeline.scrape_articles_menu()

    print("=" * 70)
    print("DISCOVERED FILMS AND ARTICLES")
    print("=" * 70)

    total_articles = 0
    for i, film in enumerate(films_data, 1):
        article_count = len(film["articles"])
        total_articles += article_count

        print(f"\n{i}. {film['film_title']}")
        print(f"   Slug: {film['film_slug']}")
        print(f"   Articles: {article_count}")

        if args.verbose:
            for j, article in enumerate(film["articles"], 1):
                print(f"     {j}. {article['title']}")
                print(f"        {article['url']}")

    print(f"\n{'=' * 70}")
    print(f"Total: {len(films_data)} films, {total_articles} articles")
    print(f"{'=' * 70}")

    return 0


def cmd_stats(args):
    """Show storage statistics."""
    settings = load_settings()

    store = ArticleJsonStore(settings.out_dir)

    print(store.generate_report())

    # Image stats
    if settings.images_dir.exists():
        from .image_downloader import ImageDownloader
        images = ImageDownloader(settings.images_dir)
        img_stats = images.get_stats()

        print(f"\nImage Storage:")
        print(f"  Files:   {img_stats['total_images']}")
        print(f"  Size:    {img_stats['total_size_mb']:.1f} MB")

    return 0


def cmd_login(args):
    """Test authentication and cache session."""
    settings = load_settings(
        override_username=args.username,
        override_password=args.password,
    )

    from .auth import authenticate_from_settings

    try:
        auth_handler = authenticate_from_settings(settings)
        print(f"\n✓ Session cached to: {settings.session_cookie_file}")
        return 0
    except Exception as e:
        print(f"\n✗ Authentication failed: {e}")
        return 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Deakins Articles Scraper - Scrape 'Looks at Lighting' articles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # scrape-all command
    p_scrape_all = subparsers.add_parser(
        "scrape-all",
        help="Scrape all articles from all films"
    )
    p_scrape_all.add_argument("--username", help="WordPress username")
    p_scrape_all.add_argument("--password", help="WordPress password")
    p_scrape_all.add_argument("--max-films", type=int, default=0, help="Max films to scrape (0=all)")
    p_scrape_all.add_argument("--max-articles", type=int, default=0, help="Max articles per film (0=all)")
    p_scrape_all.set_defaults(func=cmd_scrape_all)

    # scrape-film command
    p_scrape_film = subparsers.add_parser(
        "scrape-film",
        help="Scrape all articles for a specific film"
    )
    p_scrape_film.add_argument("film_slug", help="Film slug (e.g., 'bladerunner-2049')")
    p_scrape_film.add_argument("--username", help="WordPress username")
    p_scrape_film.add_argument("--password", help="WordPress password")
    p_scrape_film.add_argument("--max-articles", type=int, default=0, help="Max articles (0=all)")
    p_scrape_film.set_defaults(func=cmd_scrape_film)

    # scrape-article command
    p_scrape_article = subparsers.add_parser(
        "scrape-article",
        help="Scrape a single article"
    )
    p_scrape_article.add_argument("url", help="Article URL")
    p_scrape_article.add_argument("--username", help="WordPress username")
    p_scrape_article.add_argument("--password", help="WordPress password")
    p_scrape_article.add_argument("--film-slug", help="Film slug (optional, will be inferred)")
    p_scrape_article.add_argument("--force", action="store_true", help="Force re-scrape even if exists")
    p_scrape_article.set_defaults(func=cmd_scrape_article)

    # list-films command
    p_list = subparsers.add_parser(
        "list-films",
        help="List all discovered films and articles"
    )
    p_list.add_argument("--username", help="WordPress username")
    p_list.add_argument("--password", help="WordPress password")
    p_list.add_argument("--verbose", "-v", action="store_true", help="Show article details")
    p_list.set_defaults(func=cmd_list_films)

    # stats command
    p_stats = subparsers.add_parser(
        "stats",
        help="Show storage statistics"
    )
    p_stats.set_defaults(func=cmd_stats)

    # login command
    p_login = subparsers.add_parser(
        "login",
        help="Test authentication and cache session"
    )
    p_login.add_argument("--username", required=True, help="WordPress username")
    p_login.add_argument("--password", required=True, help="WordPress password")
    p_login.set_defaults(func=cmd_login)

    # Parse arguments
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Execute command
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
