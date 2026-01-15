# Quick Start Guide - Deakins Forums Ultra-Structured Scraper

## What You Have

An advanced forum scraping system that:
- Saves each post as a separate, richly-structured JSON file
- Extracts links, quotes, media, and content blocks
- Provides full-text search with SQLite FTS5
- Supports incremental updates (won't re-download unchanged content)
- Can be interrupted and resumed
- Tracks complete provenance and integrity

## Installation (Already Done!)

The system is already installed. Just activate the virtual environment:

```bash
cd /Users/yuri/ojfbot/purefoy
source venv/bin/activate
```

Dependencies installed:
- ✅ requests
- ✅ beautifulsoup4
- ✅ python-dateutil
- ✅ pydantic

## First Steps

### 1. Check Current Status

```bash
python -m deakins_forums.cli stats
```

This shows you what's already been scraped (if anything).

### 2. Test with a Single Topic

Start small to see how it works:

```bash
python -m deakins_forums.cli scrape-topic \
  "https://rogerdeakins.com/forums/topic/gaining-set-experience/" \
  --build-index
```

This will:
- Scrape all pages of that topic
- Save each post as `library/forums/posts/<post_id>.json`
- Save topic metadata as `library/forums/topics/<forum>__<topic>.json`
- Build a search index

### 3. Search What You Scraped

```bash
python -m deakins_forums.cli search "cinematography" --limit 5
```

You'll see:
- Matching posts with snippets
- Author and post metadata
- Links to original posts

### 4. Scrape a Full Forum

Once you're comfortable, scrape a complete forum:

```bash
# Scrape the Team Deakins forum (start with a small limit)
python -m deakins_forums.cli scrape-forum team-deakins \
  --max-topics 20 \
  --build-index
```

This will:
- Discover all topics in the forum
- Scrape each topic (all pages)
- Save all posts
- Build/update the search index

## Common Commands

### Scraping

```bash
# Scrape a single topic
python -m deakins_forums.cli scrape-topic "URL" --build-index

# Scrape a forum (with limits for safety)
python -m deakins_forums.cli scrape-forum SLUG \
  --max-topics 50 \
  --max-pages 10 \
  --build-index

# Scrape ALL forums (WARNING: lots of data!)
python -m deakins_forums.cli scrape-all \
  --max-forums 2 \
  --max-topics 10 \
  --build-index
```

### Searching

```bash
# Basic search
python -m deakins_forums.cli search "lighting techniques"

# Filter by forum
python -m deakins_forums.cli search "camera" --forum team-deakins

# Filter by author
python -m deakins_forums.cli search "tips" --author "Roger Deakins"

# Combine filters
python -m deakins_forums.cli search "anamorphic" \
  --forum team-deakins \
  --author "Roger" \
  --limit 10
```

### Maintenance

```bash
# Rebuild search index (after manual changes or updates)
python -m deakins_forums.cli build-index

# Check statistics
python -m deakins_forums.cli stats
```

## Understanding the Output

### Directory Structure

```
library/forums/
├── posts/           # One JSON file per post
│   ├── 175763.json
│   ├── 175764.json
│   └── ...
├── topics/          # Topic metadata with post indices
│   ├── team-deakins__gaining-experience.json
│   └── ...
├── forums/          # Forum metadata with topic lists
│   ├── team-deakins.json
│   └── ...
└── _site/           # Internal state
    ├── http_state.json      # ETag/Last-Modified cache
    ├── kb.sqlite            # Search index
    └── forums_index.json    # Main forum list
```

### Post JSON Structure

Each post file contains:
- **ids**: post_id, forum_slug, topic_slug, reply_permalink
- **author**: display_name, role (Keymaster, Participant, etc.)
- **timestamps**: raw text, parsed ISO 8601, parse confidence
- **content_text**: Plain text content
- **content_html**: Original HTML (if available)
- **blocks**: Structured content (paragraphs, quotes, lists, code)
- **quotes**: Extracted quotes with attribution
- **links**: All links (internal/external)
- **media**: Images and attachments
- **provenance**: Source URL, scrape timestamp, HTTP metadata
- **integrity**: Content hash, parser version

## Tips for Success

### 1. Start Small
Always test with a single topic or small forum first:
```bash
python -m deakins_forums.cli scrape-forum test-forum --max-topics 5
```

### 2. Monitor Progress
The scraper prints progress as it goes. Watch for:
- HTTP errors (will retry automatically)
- Rate limiting (increase delay if needed)
- Parse failures (check forum structure)

### 3. Incremental Updates
Run the same command again to update:
```bash
# First run: downloads everything
python -m deakins_forums.cli scrape-forum team-deakins

# Later: only fetches changed content (via ETag/Last-Modified)
python -m deakins_forums.cli scrape-forum team-deakins
```

### 4. Be Respectful
- Default 3-second delay between requests (don't decrease!)
- Don't run multiple scrapers simultaneously
- Respect the site's terms of service
- This is for personal educational use only

### 5. Interrupted Scraping
If scraping is interrupted:
- Press Ctrl+C to stop
- Progress is automatically saved
- Just run the same command again to continue

## Programmatic Access

Use the data in your own Python scripts:

```python
from deakins_forums.store_json import JsonLeafStore
from deakins_forums.index_sqlite import SqliteIndex
from pathlib import Path

# Initialize
store = JsonLeafStore(Path("library/forums"))
index = SqliteIndex(Path("library/forums/_site/kb.sqlite"))

# Search posts
results = index.search_posts("cinematography techniques", limit=10)
for r in results:
    print(f"Post #{r['post_id']}: {r['snippet']}")

# Load specific post
post = store.read_post("175763")
print(f"Author: {post.author.display_name}")
print(f"Content: {post.content_text}")
print(f"Links: {len(post.links)}")
print(f"Quotes: {len(post.quotes)}")

# List all posts
all_posts = store.list_all_posts()
print(f"Total posts: {len(all_posts)}")

# Statistics
stats = index.get_stats()
print(f"Indexed: {stats['total_posts']} posts from {stats['total_authors']} authors")
```

## Troubleshooting

### "No such module: deakins_forums"
Make sure you're in the project directory and venv is activated:
```bash
cd /Users/yuri/ojfbot/purefoy
source venv/bin/activate
```

### "No results found" when searching
Build the index first:
```bash
python -m deakins_forums.cli build-index
```

### Rate limiting errors (HTTP 429)
Increase the delay:
```bash
export DEAKINS_DELAY_S="5.0"
python -m deakins_forums.cli scrape-forum ...
```

### Parse errors
The forum structure may have changed. Check the HTML and update `parser_bbpress.py` if needed.

## Next Steps

1. ✅ Test with a single topic
2. ✅ Try searching
3. ✅ Scrape a small forum (5-10 topics)
4. ✅ Explore the JSON data structure
5. ✅ Scale up to larger forums
6. ✅ Write custom analysis scripts

## Full Documentation

- **Ultra-structured scraper**: `deakins_forums/README.md`
- **Main README**: `README.md`
- **Architecture details**: See inline docstrings in each module

## Getting Help

Check:
1. This quickstart
2. `deakins_forums/README.md` for detailed docs
3. `python -m deakins_forums.cli --help` for command help
4. Module docstrings in the code

Happy scraping! 🎬
