"""
Playwright-based cookie extractor for rogerdeakins.com member session.

Usage (one-time setup):
    python -m deakins_forums.cli auth-setup

This script:
1. Tries to launch Chromium using your existing Chrome profile (already logged in).
2. Falls back to an interactive non-headless browser if the profile is missing/stale.
3. Waits until a member-only page is accessible (confirms auth).
4. Exports rogerdeakins.com cookies to session_cookies.json (gitignored).

The saved cookies are then loaded by HttpClient for all subsequent article fetches.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# macOS default Chrome user data directory (contains your existing logged-in session)
CHROME_PROFILE_MACOS = Path.home() / "Library" / "Application Support" / "Google" / "Chrome"
CHROME_PROFILE_LINUX = Path.home() / ".config" / "google-chrome"
CHROME_PROFILE_WIN = Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "User Data"

# A member-only LAL page used to verify authentication
MEMBER_VERIFY_URL = "https://www.rogerdeakins.com/lal-sicario-tunnel-and-alejandros-revenge/"
AUTH_SELECTOR = ".entry-content"  # Present when logged in and content is accessible
RESTRICTED_SELECTOR = "#wpmem_restricted_msg"  # Present when NOT logged in
LOGIN_URL = "https://www.rogerdeakins.com/wp-login.php"
COOKIE_DOMAIN = "rogerdeakins.com"
AUTH_TIMEOUT_MS = 300_000  # 5 minutes for manual login if needed


def _find_chrome_profile() -> Path | None:
    for candidate in (CHROME_PROFILE_MACOS, CHROME_PROFILE_LINUX, CHROME_PROFILE_WIN):
        if candidate.exists():
            return candidate
    return None


def save_session_cookies(project_root: Path = Path(".")) -> Path:
    """
    Launch Playwright, verify member access, and save cookies.

    Returns the path to the written session_cookies.json file.
    """
    try:
        from playwright.sync_api import TimeoutError as PWTimeout
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright is not installed.")
        print("  Run: pip install playwright && playwright install chromium")
        sys.exit(1)

    out_path = project_root / "session_cookies.json"

    chrome_profile = _find_chrome_profile()
    context = None
    browser = None

    with sync_playwright() as pw:
        # --- Strategy 1: Use existing Chrome profile (already logged in) ---
        if chrome_profile:
            print(f"Trying existing Chrome profile: {chrome_profile}")
            print("  (This reuses your existing browser session — no login needed if already logged in)")
            try:
                context = pw.chromium.launch_persistent_context(
                    user_data_dir=str(chrome_profile),
                    headless=False,
                    channel="chrome",  # Use the actual installed Chrome
                    args=["--no-first-run", "--no-default-browser-check"],
                )
                page = context.new_page()
                page.goto(MEMBER_VERIFY_URL, wait_until="domcontentloaded", timeout=30_000)

                # Check auth status
                if page.query_selector(RESTRICTED_SELECTOR):
                    print("  Session not authenticated — falling through to interactive login.")
                    context.close()
                    context = None
                elif page.query_selector(AUTH_SELECTOR):
                    print("  ✓ Authenticated via existing Chrome profile!")
                else:
                    # Unknown state — still try to extract cookies
                    print("  Auth state unclear — extracting cookies anyway.")

            except Exception as e:
                print(f"  Chrome profile launch failed ({e}) — falling back to interactive login.")
                if context:
                    context.close()
                    context = None

        # --- Strategy 2: Interactive login in a fresh browser window ---
        if context is None:
            print("\nLaunching interactive browser for manual login...")
            print(f"  Please log in at: {LOGIN_URL}")
            print(f"  After logging in, navigate to: {MEMBER_VERIFY_URL}")
            print("  The script will automatically detect when you're in and save your cookies.")
            print("  You have 5 minutes. Press Ctrl+C to abort.\n")

            browser = pw.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()
            page.goto(LOGIN_URL, wait_until="domcontentloaded")

            # Wait for the user to log in and land on a member page
            print("  Waiting for authentication...")
            try:
                page.wait_for_selector(AUTH_SELECTOR, timeout=AUTH_TIMEOUT_MS)
                print("  ✓ Authenticated! Member content is now accessible.")
            except PWTimeout:
                print("ERROR: Timed out waiting for login. Please try again.")
                context.close()
                if browser:
                    browser.close()
                sys.exit(1)

        # --- Extract cookies ---
        all_cookies = context.cookies()
        site_cookies = [
            {
                "name": c["name"],
                "value": c["value"],
                "domain": c["domain"],
                "path": c["path"],
                "secure": c.get("secure", False),
                "httpOnly": c.get("httpOnly", False),
            }
            for c in all_cookies
            if COOKIE_DOMAIN in c.get("domain", "")
        ]

        if not site_cookies:
            print("WARNING: No rogerdeakins.com cookies found. Auth may have failed.")
        else:
            print(f"\n  Found {len(site_cookies)} cookies for {COOKIE_DOMAIN}")

        # Save to file
        out_path.write_text(json.dumps(site_cookies, indent=2), encoding="utf-8")
        print(f"  ✓ Cookies saved to: {out_path}")
        print("  (This file is gitignored — never committed to the repository)")

        context.close()
        if browser:
            browser.close()

    return out_path
