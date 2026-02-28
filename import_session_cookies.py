"""
Import browser-exported session cookies into the articles scraper session format.

Usage:
    python import_session_cookies.py [--cookies session_cookies.json]

The input file should be a browser cookie export in either:
  - Netscape/EditThisCookie format (list of dicts with name/value/domain/path)
  - Cookie-Editor JSON format (list of dicts with name/value/domain)

The script converts and writes to library/articles/_site/session_cookies.json
in the format expected by deakins_articles/auth.py.

After running, verify with:
    python -m deakins_articles list-films --verbose
"""

import json
import sys
from datetime import datetime
from pathlib import Path

COOKIE_INPUT = Path("session_cookies.json")
SESSION_OUTPUT = Path("library/articles/_site/session_cookies.json")


def convert_browser_cookies(cookie_list: list) -> dict:
    """Convert browser cookie export list to auth.py session format."""
    cookies_dict = {}
    for c in cookie_list:
        if isinstance(c, dict) and "name" in c and "value" in c:
            cookies_dict[c["name"]] = c["value"]
        elif isinstance(c, (list, tuple)) and len(c) >= 2:
            cookies_dict[c[0]] = c[1]

    if not cookies_dict:
        raise ValueError("No valid cookies found in input file")

    # Warn if no WordPress auth cookies
    wp_cookies = [k for k in cookies_dict if "wordpress" in k.lower() or "wp" in k.lower()]
    if not wp_cookies:
        print("WARNING: No WordPress authentication cookies found (expected 'wordpress_*' cookies)")
        print(f"  Found cookies: {list(cookies_dict.keys())}")
    else:
        print(f"✓ Found {len(wp_cookies)} WordPress cookie(s): {wp_cookies}")

    return {
        "cookies": cookies_dict,
        "authenticated_at": datetime.now().isoformat(),
        "username": "imported-from-browser",
        "expires_at": None,
    }


def main():
    input_path = COOKIE_INPUT
    if len(sys.argv) > 2 and sys.argv[1] == "--cookies":
        input_path = Path(sys.argv[2])

    if not input_path.exists():
        print(f"✗ Cookie file not found: {input_path}")
        print("  Export cookies from your browser while logged in to rogerdeakins.com")
        print("  Then place the JSON file at:", input_path)
        sys.exit(1)

    with open(input_path) as f:
        raw = json.load(f)

    if isinstance(raw, list):
        session_data = convert_browser_cookies(raw)
    elif isinstance(raw, dict) and "cookies" in raw:
        print("✓ File is already in session format — copying as-is")
        session_data = raw
    else:
        print(f"✗ Unrecognized cookie format (type: {type(raw).__name__})")
        sys.exit(1)

    # Verify cookies actually grant member access before writing
    print("Verifying cookies against rogerdeakins.com members-only content...")
    try:
        import requests
        test_session = requests.Session()
        test_session.headers["User-Agent"] = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        for name, value in session_data["cookies"].items():
            test_session.cookies.set(name, value, domain="www.rogerdeakins.com")

        r = test_session.get(
            "https://www.rogerdeakins.com/members-only/looking-at-lighting/",
            timeout=15,
        )
        if "wp-login.php" in r.url or "restricted to site members" in r.text.lower():
            print("✗ Cookies are EXPIRED or INVALID — cannot access members-only content")
            print("  Please export fresh cookies from your browser while logged in,")
            print("  or use: python -m deakins_articles login --username U --password P")
            sys.exit(1)
        print("✓ Cookies verified — members-only content is accessible")
    except Exception as e:
        print(f"⚠ Could not verify cookies (network error: {e}) — writing anyway")

    SESSION_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(SESSION_OUTPUT, "w") as f:
        json.dump(session_data, f, indent=2)

    print(f"✓ Session written to: {SESSION_OUTPUT}")
    print(f"  Cookies imported: {len(session_data['cookies'])}")
    print()
    print("Ready to scrape:")
    print("  python -m deakins_articles list-films --verbose")
    print("  python -m deakins_articles scrape-all")


if __name__ == "__main__":
    main()
