#!/usr/bin/env python3
"""
Test the article parser with sample HTML files.
"""

import sys
import json
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from deakins_articles.parser import parse_article_page


def test_parser():
    """Test parser with sample articles."""

    sample_dir = Path(__file__).parent / "sample_articles"

    if not sample_dir.exists():
        print(f"Error: {sample_dir} not found. Run test_auth.py first.")
        return False

    # Test articles
    test_files = [
        ("empire-of-light-lighting.html", "https://www.rogerdeakins.com/empire-of-light-lighting/"),
        ("skyfall-1.html", "https://www.rogerdeakins.com/skyfall-1/"),
        ("bladerunner-ks-apt-int.html", "https://www.rogerdeakins.com/bladerunner-ks-apt-int/"),
    ]

    print("=" * 70)
    print("Testing Article Parser")
    print("=" * 70)

    for filename, url in test_files:
        filepath = sample_dir / filename

        print(f"\n{'─' * 70}")
        print(f"Parsing: {filename}")
        print(f"{'─' * 70}")

        try:
            # Read HTML
            with open(filepath, "r", encoding="utf-8") as f:
                html = f.read()

            # Parse article
            raw_article = parse_article_page(
                base_url="https://www.rogerdeakins.com",
                article_url=url,
                html=html
            )

            # Display results
            print(f"\n✓ Parsed successfully!")
            print(f"\nArticle Details:")
            print(f"  ID: {raw_article.article_id}")
            print(f"  Film: {raw_article.film_slug}")
            print(f"  Slug: {raw_article.article_slug}")
            print(f"  Title: {raw_article.title}")
            print(f"  Author: {raw_article.author_name}")
            print(f"  Published: {raw_article.published_date}")
            print(f"  Modified: {raw_article.modified_date}")

            if raw_article.description:
                print(f"  Description: {raw_article.description[:100]}...")

            print(f"\nContent:")
            print(f"  HTML length: {len(raw_article.content_html):,} chars")
            print(f"  Text length: {len(raw_article.content_text):,} chars")
            print(f"  Images: {len(raw_article.raw_images)}")
            print(f"  Links: {len(raw_article.raw_links)}")

            if raw_article.featured_image_url:
                print(f"\nFeatured Image:")
                print(f"  {raw_article.featured_image_url}")

            if raw_article.raw_images:
                print(f"\nImages ({len(raw_article.raw_images)} total):")
                for i, img in enumerate(raw_article.raw_images[:3], 1):
                    print(f"  {i}. {img['src']}")
                    if img.get('caption'):
                        print(f"     Caption: {img['caption']}")
                    if img.get('width') and img.get('height'):
                        print(f"     Size: {img['width']}x{img['height']}")

                if len(raw_article.raw_images) > 3:
                    print(f"  ... and {len(raw_article.raw_images) - 3} more")

            if raw_article.tags:
                print(f"\nTags: {', '.join(raw_article.tags)}")

            if raw_article.categories:
                print(f"Categories: {', '.join(raw_article.categories)}")

            # Save parsed data for inspection
            output_file = sample_dir / f"{raw_article.article_slug}_parsed.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump({
                    "article_id": raw_article.article_id,
                    "film_slug": raw_article.film_slug,
                    "article_slug": raw_article.article_slug,
                    "title": raw_article.title,
                    "author": raw_article.author_name,
                    "published_date": raw_article.published_date,
                    "modified_date": raw_article.modified_date,
                    "description": raw_article.description,
                    "featured_image": raw_article.featured_image_url,
                    "content_length": len(raw_article.content_text),
                    "images_count": len(raw_article.raw_images),
                    "links_count": len(raw_article.raw_links),
                    "tags": raw_article.tags,
                    "categories": raw_article.categories,
                    "images": raw_article.raw_images[:5],  # First 5 images
                    "links": raw_article.raw_links[:5],  # First 5 links
                }, f, indent=2)

            print(f"\n✓ Saved parsed data to: {output_file}")

        except Exception as e:
            print(f"\n✗ Error parsing: {e}")
            import traceback
            traceback.print_exc()
            return False

    print(f"\n{'=' * 70}")
    print(f"✓ All articles parsed successfully!")
    print(f"{'=' * 70}")

    return True


if __name__ == "__main__":
    success = test_parser()
    sys.exit(0 if success else 1)
