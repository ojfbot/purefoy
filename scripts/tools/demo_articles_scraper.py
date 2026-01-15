#!/usr/bin/env python3
"""
Demonstration of the articles scraper.

This script demonstrates the complete pipeline by scraping a few
representative films from the "Looks at Lighting" collection.
"""

import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from deakins_articles.config import load_settings
from deakins_articles.pipeline import build_pipeline


def demo_scrape():
    """
    Demonstration scraping run.

    Scrapes 3 films with varying article counts:
    - 1984 (1 article)
    - The Assassination of Jesse James (3 articles)
    - True Grit Lighting (1 article)

    Total: 5 articles to demonstrate the system.
    """
    print("=" * 70)
    print("DEAKINS ARTICLES SCRAPER - DEMONSTRATION")
    print("=" * 70)

    # Load settings
    settings = load_settings(
        override_username="TelevisionSky",
        override_password="hIhru6-kokxak-gebgom",
    )

    print(f"\nConfiguration:")
    print(f"  Username: {settings.username}")
    print(f"  Output: {settings.out_dir}")
    print(f"  Images: {settings.images_dir}")

    # Build pipeline
    print(f"\nInitializing pipeline...")
    try:
        pipeline = build_pipeline(settings)
    except Exception as e:
        print(f"✗ Failed to initialize: {e}")
        return 1

    # Discover all films
    print(f"\nDiscovering films...")
    films_data = pipeline.scrape_articles_menu()

    print(f"✓ Discovered {len(films_data)} films")

    # Select films to scrape
    demo_films = ["1984", "the-assassination-of-jesse-james", "true-grit-lighting"]

    print(f"\nDemo will scrape {len(demo_films)} films:")
    for film_slug in demo_films:
        film_data = next((f for f in films_data if f["film_slug"] == film_slug), None)
        if film_data:
            print(f"  - {film_data['film_title']} ({len(film_data['articles'])} articles)")

    input("\nPress Enter to start scraping...")

    # Scrape each demo film
    film_sections = []
    for i, film_slug in enumerate(demo_films, 1):
        film_data = next((f for f in films_data if f["film_slug"] == film_slug), None)
        if not film_data:
            print(f"\n✗ Film not found: {film_slug}")
            continue

        print(f"\n{'#' * 70}")
        print(f"DEMO FILM {i}/{len(demo_films)}")
        print(f"{'#' * 70}")

        film_section = pipeline.scrape_film(
            film_slug=film_data["film_slug"],
            film_title=film_data["film_title"],
            articles=film_data["articles"],
        )

        if film_section:
            film_sections.append(film_section)

    # Generate statistics
    total_articles = sum(f.article_count for f in film_sections)
    total_images = sum(f.total_images for f in film_sections)

    # Show results
    print("\n" + "=" * 70)
    print("DEMONSTRATION COMPLETE")
    print("=" * 70)
    print(f"Films scraped:    {len(film_sections)}")
    print(f"Articles scraped: {total_articles}")
    print(f"Images downloaded: {total_images}")
    print("=" * 70)

    # Show file locations
    print(f"\nOutput locations:")
    print(f"  Articles: {settings.out_dir / 'articles/'}")
    print(f"  Films:    {settings.out_dir / 'films/'}")
    print(f"  Images:   {settings.images_dir}")

    # Show sample commands
    print(f"\nNext steps:")
    print(f"  # View statistics")
    print(f"  python3 -m deakins_articles stats")
    print(f"")
    print(f"  # Scrape more films")
    print(f"  python3 -m deakins_articles scrape-film bladerunner-2049 --username ... --password ...")
    print(f"")
    print(f"  # Scrape ALL articles (84 total)")
    print(f"  python3 -m deakins_articles scrape-all --username ... --password ...")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(demo_scrape())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
