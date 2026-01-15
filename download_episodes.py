#!/usr/bin/env python3
"""
Team Deakins Podcast Episode Downloader

FAIR USE NOTICE:
This script is intended for personal research, educational, and creative coding
purposes only. All content downloaded remains the property of its respective
copyright holders (Team Deakins podcast and its creators).

IMPORTANT:
- This tool is for personal archival and research use only
- All commercial use requires explicit permission from copyright holders
- Users must respect all copyright and intellectual property rights
- Downloaded content should not be redistributed without permission
- This is provided as-is for educational/research purposes under fair use principles

By using this script, you acknowledge that you will:
1. Obtain proper licensing for any commercial use
2. Respect all copyright and intellectual property rights
3. Use downloaded content only for permitted personal/research purposes
4. Not redistribute content without authorization

For questions about commercial licensing, contact Team Deakins directly.
"""

import os
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configuration
RSS_FEED_URL = "https://rss.libsyn.com/shows/265448/destinations/2018942.xml"
DOWNLOAD_DIR = Path(__file__).parent / "downloads"
USER_AGENT = "Mozilla/5.0 (Educational Research Bot; Fair Use; +contact@research.edu)"
RATE_LIMIT_DELAY = 2  # seconds between downloads

def setup_session():
    """Create a requests session with retry logic and appropriate headers."""
    session = requests.Session()

    # Fair use and research identification headers
    session.headers.update({
        'User-Agent': USER_AGENT,
        'Accept': '*/*',
        'X-Research-Purpose': 'Educational and creative coding research',
        'X-Fair-Use': 'Personal archival for non-commercial research'
    })

    # Retry strategy for network resilience
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session

def fetch_rss_feed(session):
    """Fetch and parse the RSS feed."""
    print("Fetching RSS feed...")
    try:
        response = session.get(RSS_FEED_URL, timeout=30)
        response.raise_for_status()
        return ET.fromstring(response.content)
    except Exception as e:
        print(f"Error fetching RSS feed: {e}")
        sys.exit(1)

def parse_episodes(root):
    """Extract episode information from RSS feed."""
    episodes = []

    for item in root.findall('.//item'):
        title = item.find('title')
        enclosure = item.find('enclosure')
        pub_date = item.find('pubDate')

        if enclosure is not None and 'url' in enclosure.attrib:
            mp3_url = enclosure.attrib['url']
            episode_title = title.text if title is not None else "Unknown"
            date = pub_date.text if pub_date is not None else "Unknown"

            # Extract filename from URL
            filename = os.path.basename(urlparse(mp3_url).path)

            episodes.append({
                'title': episode_title,
                'url': mp3_url,
                'filename': filename,
                'date': date
            })

    # Reverse to get oldest first
    episodes.reverse()

    return episodes

def sanitize_filename(filename):
    """Ensure filename is safe for filesystem."""
    # Remove or replace problematic characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename

def download_episode(session, episode, download_dir):
    """Download a single episode."""
    filepath = download_dir / sanitize_filename(episode['filename'])

    # Skip if already exists
    if filepath.exists():
        print(f"✓ Already downloaded: {episode['filename']}")
        return True

    print(f"\nDownloading: {episode['title']}")
    print(f"  Date: {episode['date']}")
    print(f"  File: {episode['filename']}")

    try:
        # Stream download to handle large files
        response = session.get(episode['url'], stream=True, timeout=60)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))

        with open(filepath, 'wb') as f:
            if total_size == 0:
                f.write(response.content)
            else:
                downloaded = 0
                chunk_size = 8192
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        # Simple progress indicator
                        percent = (downloaded / total_size) * 100
                        print(f"  Progress: {percent:.1f}% ({downloaded // 1024 // 1024}MB / {total_size // 1024 // 1024}MB)", end='\r')

        print(f"\n✓ Downloaded successfully: {episode['filename']}")
        return True

    except Exception as e:
        print(f"\n✗ Error downloading {episode['filename']}: {e}")
        # Clean up partial download
        if filepath.exists():
            filepath.unlink()
        return False

def main():
    """Main execution function."""
    print("=" * 70)
    print("Team Deakins Podcast Episode Downloader")
    print("=" * 70)
    print("\nFAIR USE NOTICE:")
    print("This script is for personal research and educational purposes only.")
    print("All content remains property of Team Deakins and its copyright holders.")
    print("Commercial use requires explicit permission from copyright holders.")
    print("=" * 70)

    # Ensure download directory exists
    DOWNLOAD_DIR.mkdir(exist_ok=True)
    print(f"\nDownload directory: {DOWNLOAD_DIR}")

    # Setup session with fair use headers
    session = setup_session()

    # Fetch and parse RSS feed
    root = fetch_rss_feed(session)
    episodes = parse_episodes(root)

    print(f"\nFound {len(episodes)} episodes in feed")
    print("Starting downloads (oldest to newest)...\n")

    # Download episodes
    success_count = 0
    failed_count = 0
    skipped_count = 0

    for i, episode in enumerate(episodes, 1):
        print(f"\n[{i}/{len(episodes)}] ", end='')

        filepath = DOWNLOAD_DIR / sanitize_filename(episode['filename'])
        if filepath.exists():
            skipped_count += 1
            print(f"✓ Already exists: {episode['filename']}")
            continue

        if download_episode(session, episode, DOWNLOAD_DIR):
            success_count += 1
        else:
            failed_count += 1

        # Rate limiting - be respectful to the server
        if i < len(episodes):
            time.sleep(RATE_LIMIT_DELAY)

    # Summary
    print("\n" + "=" * 70)
    print("Download Summary:")
    print(f"  Total episodes: {len(episodes)}")
    print(f"  Successfully downloaded: {success_count}")
    print(f"  Already existed: {skipped_count}")
    print(f"  Failed: {failed_count}")
    print("=" * 70)

    if failed_count > 0:
        print("\nSome downloads failed. You can re-run this script to retry.")
        sys.exit(1)
    else:
        print("\n✓ All episodes processed successfully!")
        sys.exit(0)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nDownload interrupted by user. You can re-run to continue.")
        sys.exit(130)
