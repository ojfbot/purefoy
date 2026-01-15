#!/usr/bin/env python3
"""
Roger Deakins Forum Scraper

FAIR USE NOTICE:
This script is intended for personal research, educational, and creative coding
purposes only. All content downloaded remains the property of its respective
copyright holders (rogerdeakins.com and its contributors).

IMPORTANT:
- This tool is for personal archival and research use only
- All commercial use requires explicit permission from copyright holders
- Users must respect all copyright and intellectual property rights
- Downloaded content should not be redistributed without permission
- This is provided as-is for educational/research purposes under fair use principles
- Rate limiting is implemented to be respectful to the server

By using this script, you acknowledge that you will:
1. Obtain proper licensing for any commercial use
2. Respect all copyright and intellectual property rights
3. Use downloaded content only for permitted personal/research purposes
4. Not redistribute content without authorization
5. Respect robots.txt and server resources

For questions about commercial licensing, contact rogerdeakins.com directly.
"""

import os
import sys
import time
import json
import hashlib
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs
from urllib.robotparser import RobotFileParser
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

# Configuration
BASE_URL = "https://rogerdeakins.com/forums/"
FORUM_URL = "https://rogerdeakins.com/forums/"
OUTPUT_DIR = Path(__file__).parent / "library" / "forums"
USER_AGENT = "Mozilla/5.0 (Educational Research Bot; Fair Use; Cinematography Education)"
RATE_LIMIT_DELAY = 3  # seconds between requests (be respectful!)
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3

# Progress tracking
PROGRESS_FILE = OUTPUT_DIR / "scrape_progress.json"
VISITED_URLS_FILE = OUTPUT_DIR / "visited_urls.json"

class ForumScraper:
    """Scraper for Roger Deakins forum content."""

    def __init__(self):
        self.session = self._setup_session()
        self.visited_urls = set()
        self.progress = {
            'last_run': None,
            'total_pages': 0,
            'total_topics': 0,
            'total_posts': 0,
            'errors': []
        }
        self.robots_parser = None

        # Load previous progress if exists
        self._load_progress()
        self._check_robots_txt()

    def _setup_session(self):
        """Create a requests session with retry logic and appropriate headers."""
        session = requests.Session()

        # Fair use and research identification headers
        session.headers.update({
            'User-Agent': USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })

        # Retry strategy for network resilience
        retry_strategy = Retry(
            total=MAX_RETRIES,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def _check_robots_txt(self):
        """Check and respect robots.txt."""
        print("Checking robots.txt...")
        try:
            robots_url = urljoin(BASE_URL, '/robots.txt')
            self.robots_parser = RobotFileParser()
            self.robots_parser.set_url(robots_url)
            self.robots_parser.read()

            if self.robots_parser.can_fetch(USER_AGENT, FORUM_URL):
                print("✓ robots.txt allows crawling")
            else:
                print("✗ robots.txt disallows crawling this area")
                print("Please respect the website's robots.txt")
                sys.exit(1)
        except Exception as e:
            print(f"Warning: Could not fetch robots.txt: {e}")
            print("Proceeding with caution...")

    def _load_progress(self):
        """Load previous scraping progress."""
        if PROGRESS_FILE.exists():
            with open(PROGRESS_FILE, 'r') as f:
                self.progress = json.load(f)
            print(f"Loaded previous progress: {self.progress['total_pages']} pages scraped")

        if VISITED_URLS_FILE.exists():
            with open(VISITED_URLS_FILE, 'r') as f:
                self.visited_urls = set(json.load(f))
            print(f"Loaded {len(self.visited_urls)} previously visited URLs")

    def _save_progress(self):
        """Save scraping progress."""
        self.progress['last_run'] = datetime.now().isoformat()

        OUTPUT_DIR.mkdir(exist_ok=True)

        with open(PROGRESS_FILE, 'w') as f:
            json.dump(self.progress, f, indent=2)

        with open(VISITED_URLS_FILE, 'w') as f:
            json.dump(list(self.visited_urls), f, indent=2)

    def _get_url_hash(self, url):
        """Generate a hash for a URL to use as filename."""
        return hashlib.md5(url.encode()).hexdigest()

    def _sanitize_filename(self, text, max_length=100):
        """Create a safe filename from text."""
        # Remove invalid characters
        invalid_chars = '<>:"/\\|?*\n\r\t'
        for char in invalid_chars:
            text = text.replace(char, '_')

        # Limit length
        text = text[:max_length]

        # Remove leading/trailing spaces and dots
        text = text.strip('. ')

        return text or "unnamed"

    def _is_forum_url(self, url):
        """Check if URL is a forum page."""
        parsed = urlparse(url)
        return 'rogerdeakins.com/forums' in url.lower()

    def _should_crawl(self, url):
        """Determine if we should crawl this URL."""
        # Already visited
        if url in self.visited_urls:
            return False

        # Check if it's a forum URL
        if not self._is_forum_url(url):
            return False

        # Check robots.txt
        if self.robots_parser and not self.robots_parser.can_fetch(USER_AGENT, url):
            return False

        # Skip certain URL patterns (downloads, attachments, admin pages)
        skip_patterns = [
            'action=',
            'download',
            'attachment',
            'admin',
            'login',
            'register',
            'profile',
            'memberlist',
            'search.php',
        ]

        for pattern in skip_patterns:
            if pattern in url.lower():
                return False

        return True

    def fetch_page(self, url):
        """Fetch a page with rate limiting and error handling."""
        if url in self.visited_urls:
            return None

        print(f"\nFetching: {url}")

        try:
            # Rate limiting
            time.sleep(RATE_LIMIT_DELAY)

            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()

            self.visited_urls.add(url)
            self.progress['total_pages'] += 1

            return response.text

        except requests.exceptions.RequestException as e:
            error_msg = f"Error fetching {url}: {e}"
            print(f"✗ {error_msg}")
            self.progress['errors'].append({
                'url': url,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
            return None

    def parse_forum_index(self, html, url):
        """Parse forum index to find board URLs."""
        soup = BeautifulSoup(html, 'html.parser')

        boards = []

        # Look for forum board links (phpBB structure)
        for link in soup.find_all('a', href=True):
            href = link['href']
            full_url = urljoin(url, href)

            # Find board links (typically viewforum.php?f=X)
            if 'viewforum.php' in href and 'f=' in href:
                board_name = link.get_text(strip=True)
                boards.append({
                    'url': full_url,
                    'name': board_name
                })

        return boards

    def parse_board(self, html, url):
        """Parse a board page to find topic URLs."""
        soup = BeautifulSoup(html, 'html.parser')

        topics = []

        # Find topic links (typically viewtopic.php?f=X&t=Y)
        for link in soup.find_all('a', href=True):
            href = link['href']
            full_url = urljoin(url, href)

            if 'viewtopic.php' in href and 't=' in href:
                topic_title = link.get_text(strip=True)
                topics.append({
                    'url': full_url,
                    'title': topic_title
                })

        # Find pagination links
        next_page = None
        for link in soup.find_all('a', href=True):
            if 'next' in link.get_text().lower() or '→' in link.get_text():
                next_page = urljoin(url, link['href'])
                break

        return topics, next_page

    def parse_topic(self, html, url):
        """Parse a topic page and save content."""
        soup = BeautifulSoup(html, 'html.parser')

        # Extract topic information
        topic_data = {
            'url': url,
            'scraped_at': datetime.now().isoformat(),
            'title': '',
            'posts': []
        }

        # Get topic title
        title_elem = soup.find('h2') or soup.find('h1')
        if title_elem:
            topic_data['title'] = title_elem.get_text(strip=True)

        # Find all posts
        posts = soup.find_all(['div', 'article'], class_=lambda x: x and ('post' in x.lower() if isinstance(x, str) else any('post' in c.lower() for c in x)))

        for post in posts:
            post_data = {}

            # Extract author
            author = post.find(['span', 'div', 'a'], class_=lambda x: x and ('author' in x.lower() or 'username' in x.lower()) if isinstance(x, str) else False)
            if author:
                post_data['author'] = author.get_text(strip=True)

            # Extract post date
            date = post.find(['span', 'div', 'time'], class_=lambda x: x and ('date' in x.lower() or 'time' in x.lower()) if isinstance(x, str) else False)
            if date:
                post_data['date'] = date.get_text(strip=True)

            # Extract post content
            content = post.find(['div', 'article'], class_=lambda x: x and ('content' in x.lower() or 'message' in x.lower()) if isinstance(x, str) else False)
            if content:
                post_data['content'] = content.get_text(separator='\n', strip=True)
            else:
                # Fallback to all text in post
                post_data['content'] = post.get_text(separator='\n', strip=True)

            if post_data.get('content'):
                topic_data['posts'].append(post_data)

        # Save to file
        self._save_topic(topic_data)

        self.progress['total_topics'] += 1
        self.progress['total_posts'] += len(topic_data['posts'])

        # Find next page (for multi-page topics)
        next_page = None
        for link in soup.find_all('a', href=True):
            link_text = link.get_text().lower()
            if 'next' in link_text or '→' in link.get_text():
                next_page = urljoin(url, link['href'])
                break

        return next_page

    def _save_topic(self, topic_data):
        """Save topic data to JSON file."""
        # Create directory structure
        topics_dir = OUTPUT_DIR / "topics"
        topics_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename
        url_hash = self._get_url_hash(topic_data['url'])
        safe_title = self._sanitize_filename(topic_data['title'])
        filename = f"{safe_title}_{url_hash}.json"
        filepath = topics_dir / filename

        # Save JSON
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(topic_data, f, indent=2, ensure_ascii=False)

        print(f"✓ Saved: {safe_title} ({len(topic_data['posts'])} posts)")

    def scrape_board(self, board_url, board_name):
        """Scrape all topics from a board."""
        print(f"\n{'='*70}")
        print(f"Scraping board: {board_name}")
        print(f"{'='*70}")

        current_page = board_url
        page_num = 1

        while current_page and self._should_crawl(current_page):
            print(f"\n--- Board page {page_num} ---")

            html = self.fetch_page(current_page)
            if not html:
                break

            topics, next_page = self.parse_board(html, current_page)

            print(f"Found {len(topics)} topics on this page")

            # Scrape each topic
            for topic in topics:
                if self._should_crawl(topic['url']):
                    self.scrape_topic(topic['url'], topic['title'])

                    # Save progress periodically
                    if self.progress['total_topics'] % 10 == 0:
                        self._save_progress()

            current_page = next_page
            page_num += 1

    def scrape_topic(self, topic_url, topic_title):
        """Scrape all pages of a topic."""
        current_page = topic_url
        page_num = 1

        while current_page and self._should_crawl(current_page):
            if page_num > 1:
                print(f"  → Page {page_num} of topic: {topic_title}")

            html = self.fetch_page(current_page)
            if not html:
                break

            next_page = self.parse_topic(html, current_page)
            current_page = next_page
            page_num += 1

    def scrape_forum(self):
        """Main scraping function."""
        print(f"\n{'='*70}")
        print("Roger Deakins Forum Scraper")
        print(f"{'='*70}")
        print("\nFAIR USE NOTICE:")
        print("This script is for personal research and educational purposes only.")
        print("All content remains property of rogerdeakins.com and its contributors.")
        print("Commercial use requires explicit permission from copyright holders.")
        print(f"{'='*70}\n")

        # Ensure output directory exists
        OUTPUT_DIR.mkdir(exist_ok=True)
        print(f"Output directory: {OUTPUT_DIR}")

        # Fetch forum index
        print("\nFetching forum index...")
        html = self.fetch_page(FORUM_URL)
        if not html:
            print("✗ Failed to fetch forum index")
            return

        # Parse boards
        boards = self.parse_forum_index(html, FORUM_URL)
        print(f"\nFound {len(boards)} forum boards")

        # Scrape each board
        for i, board in enumerate(boards, 1):
            print(f"\n[{i}/{len(boards)}] Processing board: {board['name']}")
            self.scrape_board(board['url'], board['name'])

            # Save progress after each board
            self._save_progress()

        # Final save
        self._save_progress()

        # Print summary
        print(f"\n{'='*70}")
        print("Scraping Summary:")
        print(f"  Total pages fetched: {self.progress['total_pages']}")
        print(f"  Total topics saved: {self.progress['total_topics']}")
        print(f"  Total posts saved: {self.progress['total_posts']}")
        print(f"  Errors encountered: {len(self.progress['errors'])}")
        print(f"{'='*70}\n")

        if self.progress['errors']:
            print(f"Errors logged to: {PROGRESS_FILE}")

        print("✓ Forum scraping completed!")


def main():
    """Main execution function."""
    try:
        scraper = ForumScraper()
        scraper.scrape_forum()
    except KeyboardInterrupt:
        print("\n\nScraping interrupted by user.")
        print("Progress has been saved. You can re-run to continue.")
        sys.exit(130)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
