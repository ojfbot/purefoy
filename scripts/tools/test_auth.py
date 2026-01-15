#!/usr/bin/env python3
"""
Test authentication and fetch sample article pages.

This script authenticates with rogerdeakins.com and saves sample
article HTML so we can examine the actual structure.
"""

import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from deakins_articles.config import ArticlesSettings
from deakins_articles.auth import WordPressAuthHandler


def test_authentication(username: str, password: str):
    """Test authentication and fetch sample articles."""

    print("=" * 70)
    print("Testing Roger Deakins Authentication")
    print("=" * 70)

    # Create settings
    settings = ArticlesSettings()
    settings.username = username
    settings.password = password
    settings.ensure_directories()

    print(f"\n1. Initializing authentication handler...")
    print(f"   Base URL: {settings.base_url}")
    print(f"   Login URL: {settings.login_url}")
    print(f"   Username: {username}")

    # Create auth handler
    auth_handler = WordPressAuthHandler(
        base_url=settings.base_url,
        login_url=settings.login_url,
        session_file=settings.session_cookie_file,
        user_agent=settings.user_agent,
    )

    print(f"\n2. Authenticating...")
    try:
        auth_handler.authenticate(username, password)
        print(f"   ✓ Authentication successful!")
    except Exception as e:
        print(f"   ✗ Authentication failed: {e}")
        return False

    # Get authenticated session
    session = auth_handler.get_authenticated_session()

    # Test URLs to fetch
    test_urls = [
        "https://www.rogerdeakins.com/empire-of-light-lighting/",
        "https://www.rogerdeakins.com/skyfall-1/",
        "https://www.rogerdeakins.com/bladerunner-ks-apt-int/",
    ]

    print(f"\n3. Fetching sample articles to examine structure...")

    output_dir = Path(__file__).parent / "sample_articles"
    output_dir.mkdir(exist_ok=True)

    for i, url in enumerate(test_urls, 1):
        print(f"\n   Fetching {i}/{len(test_urls)}: {url}")

        try:
            response = session.get(url, timeout=30)
            response.raise_for_status()

            # Check if we're still authenticated
            if "restricted to site members" in response.text.lower():
                print(f"      ✗ Access denied - authentication may have failed")
                continue

            if "wp-login.php" in response.url:
                print(f"      ✗ Redirected to login - authentication issue")
                continue

            # Save HTML
            filename = url.split("/")[-2] + ".html"
            output_path = output_dir / filename

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(response.text)

            content_length = len(response.text)
            print(f"      ✓ Saved to: {output_path}")
            print(f"      ✓ Size: {content_length:,} bytes")

            # Quick analysis
            html_lower = response.text.lower()
            has_images = response.text.count("<img") > 0
            has_content = "entry-content" in html_lower or "article" in html_lower

            print(f"      ✓ Contains images: {has_images}")
            print(f"      ✓ Has article content: {has_content}")

        except Exception as e:
            print(f"      ✗ Error: {e}")

    print(f"\n{'=' * 70}")
    print(f"Sample articles saved to: {output_dir}")
    print(f"Examine these files to understand the HTML structure")
    print(f"{'=' * 70}")

    return True


if __name__ == "__main__":
    import getpass

    print("\nRoger Deakins Articles - Authentication Test")
    print("-" * 50)

    # Get credentials
    username = input("Username (or press Enter for 'TelevisionSky'): ").strip()
    if not username:
        username = "TelevisionSky"

    password = getpass.getpass(f"Password for {username}: ")

    if not password:
        print("Error: Password is required")
        sys.exit(1)

    success = test_authentication(username, password)

    sys.exit(0 if success else 1)
