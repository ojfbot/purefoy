# Deakins Forums Knowledge Base

An **ultra-structured**, **composable**, **MCP-ready** forum scraper for rogerdeakins.com/forums.

## Design Principles

### 1. Ultra-Structured Data
Each entity (post, topic, forum) is stored as a separate JSON "leaf" file with comprehensive metadata:
- **Posts**: `posts/<post_id>.json` with author, timestamps, content blocks, extracted links/media/quotes
- **Topics**: `topics/<forum>__<topic>.json` with post indices and metadata
- **Forums**: `forums/<forum_slug>.json` with topic lists and subforums

### 2. Composable Architecture
Clean separation of concerns across layers:
- **HTTP Client**: Rate limiting, retries, conditional GET (ETag/Last-Modified)
- **Parser**: bbPress-specific extraction logic for forums/topics/posts
- **Normalizer**: Structured content extraction (links, quotes, media, blocks)
- **Store**: JSON leaf persistence with deterministic paths
- **Index**: SQLite FTS5 for fast full-text search
- **Pipeline**: High-level orchestration
- **CLI**: Command-line interface
- **MCP**: Model Context Protocol server (coming soon)

### 3. Incremental & Respectful
- **Conditional GET**: Uses ETag/Last-Modified to avoid re-downloading unchanged pages
- **Content hashing**: Detects changes for incremental updates
- **Rate limiting**: Configurable delays between requests (default: 3s)
- **robots.txt**: Respects crawling policies
- **Resume capability**: Progress is saved; scraping can be interrupted and resumed

### 4. Agent-Friendly
- **Structured extraction**: Posts include content blocks, quotes with attribution, extracted links
- **Full-text search**: SQLite FTS5 with snippet extraction and relevance ranking
- **Stable identifiers**: Post IDs from the forum (visible as `#<id>` tokens)
- **Provenance tracking**: Every leaf includes source URL, scrape timestamp, HTTP metadata
- **Integrity checking**: Content hashes for change detection

## Quick Start

### Installation

```bash
# From the project root
cd purefoy

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Or install in development mode
pip install -e .
```

### Basic Usage

```bash
# Show statistics
python -m deakins_forums.cli stats

# Scrape a single topic
python -m deakins_forums.cli scrape-topic \
  "https://rogerdeakins.com/forums/topic/gaining-set-experience/"

# Scrape a single forum
python -m deakins_forums.cli scrape-forum team-deakins \
  --max-topics 50 --build-index

# Scrape all forums (careful - this is a lot of data!)
python -m deakins_forums.cli scrape-all \
  --max-forums 2 --max-topics 10 --build-index

# Build/rebuild search index
python -m deakins_forums.cli build-index

# Search
python -m deakins_forums.cli search "lighting techniques" --limit 10
python -m deakins_forums.cli search "anamorphic lens" --forum team-deakins
python -m deakins_forums.cli search "color grading" --author "Roger Deakins"
```

## Data Structure

### Output Directory Structure

```
library/forums/
├── posts/
│   ├── 175763.json          # Individual post leafs
│   ├── 175764.json
│   └── ...
├── topics/
│   ├── team-deakins__gaining-set-experience.json
│   ├── team-deakins__lighting-techniques.json
│   └── ...
├── forums/
│   ├── team-deakins.json
│   ├── byways.json
│   └── ...
└── _site/
    ├── forums_index.json     # Main forum list
    ├── http_state.json       # ETag/Last-Modified cache
    └── kb.sqlite             # Search index
```

### Post Leaf Schema

Each post is saved with rich metadata:

```json
{
  "ids": {
    "post_id": "175763",
    "forum_slug": "team-deakins",
    "topic_slug": "gaining-set-experience",
    "reply_permalink": "https://..."
  },
  "author": {
    "display_name": "Roger Deakins",
    "role": "Keymaster"
  },
  "timestamps": {
    "raw": "January 18, 2023 at 3:32 pm #175763",
    "parsed_iso": "2023-01-18T15:32:00",
    "parse_confidence": "medium"
  },
  "content_text": "Full post text...",
  "content_html": "<p>HTML version...</p>",
  "blocks": [
    {"type": "paragraph", "text": "..."},
    {"type": "quote", "text": "..."}
  ],
  "quotes": [
    {"text": "...", "attributed_to": "Username"}
  ],
  "links": [
    {"href": "https://...", "text": "link text", "kind": "external"}
  ],
  "media": [
    {"src": "https://...", "alt": "image description", "kind": "image"}
  ],
  "provenance": {
    "source_url": "https://...",
    "scraped_at": "2026-01-15T12:34:56Z",
    "http": {
      "url": "https://...",
      "status": 200,
      "etag": "...",
      "last_modified": "..."
    }
  },
  "integrity": {
    "content_hash": "sha256...",
    "parser_version": "bbpress-v1"
  }
}
```

## Architecture

### Layer 1: HTTP Client (`http_client.py`)
- Respectful rate limiting
- Automatic retries with exponential backoff
- Conditional GET using ETag/Last-Modified
- State persistence for incremental updates

### Layer 2: Parser (`parser_bbpress.py`)
- Forum index parsing: Discovers all forums
- Forum page parsing: Extracts topics and subforums
- Topic page parsing: Extracts posts with #<id> tokens
- Pagination detection and handling

### Layer 3: Normalizer (`normalize.py`)
- Content block extraction (paragraphs, quotes, lists, code, headings)
- Link extraction (internal/external classification)
- Media extraction (images, attachments)
- Quote extraction with attribution detection

### Layer 4: Store (`store_json.py`)
- Deterministic file paths for each entity type
- JSON serialization with Pydantic models
- Read/write operations for posts, topics, forums
- Statistics and listing operations

### Layer 5: Index (`index_sqlite.py`)
- SQLite FTS5 full-text search
- Snippet extraction with highlighting
- Relevance ranking
- Filtering by forum, author, topic
- Metadata table for structured queries

### Layer 6: Pipeline (`pipeline.py`)
- High-level orchestration
- Pagination handling for forums and topics
- Batch operations (scrape all forums)
- Progress reporting

### Layer 7: Interfaces
- **CLI** (`cli.py`): Command-line interface for all operations
- **MCP** (coming soon): Model Context Protocol server for AI agents

## Configuration

Environment variables (all optional):

```bash
export DEAKINS_BASE_URL="https://rogerdeakins.com"
export DEAKINS_USER_AGENT="Your Bot Name"
export DEAKINS_DELAY_S="3.0"           # Seconds between requests
export DEAKINS_TIMEOUT_S="30"          # Request timeout
export DEAKINS_MAX_RETRIES="3"         # Max retry attempts
export DEAKINS_OUT_DIR="library/forums" # Output directory
```

Or use the defaults in `config.py`.

## Best Practices

### 1. Start Small
```bash
# Test with a single topic first
python -m deakins_forums.cli scrape-topic \
  "https://rogerdeakins.com/forums/topic/some-topic/"

# Then try a small forum
python -m deakins_forums.cli scrape-forum test-forum \
  --max-topics 10
```

### 2. Be Respectful
- Use the default 3-second delay (or longer)
- Don't run multiple scrapers simultaneously
- Monitor for rate limiting (HTTP 429)
- Respect the site's terms of service

### 3. Incremental Updates
The scraper is designed for incremental updates:
```bash
# First run: scrapes everything
python -m deakins_forums.cli scrape-forum team-deakins

# Subsequent runs: only fetches changed pages (via ETag/Last-Modified)
python -m deakins_forums.cli scrape-forum team-deakins
```

### 4. Build Index After Scraping
```bash
# Scrape with automatic index build
python -m deakins_forums.cli scrape-forum team-deakins --build-index

# Or build/rebuild index separately
python -m deakins_forums.cli build-index
```

### 5. Search Effectively
```bash
# Basic search
python -m deakins_forums.cli search "cinematography techniques"

# Filter by forum
python -m deakins_forums.cli search "lighting" --forum team-deakins

# Filter by author
python -m deakins_forums.cli search "tips" --author "Roger Deakins"

# Combine filters
python -m deakins_forums.cli search "camera settings" \
  --forum team-deakins --author "Roger" --limit 5
```

## Development

### Running Tests
```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests (coming soon)
pytest tests/
```

### Code Style
```bash
# Format code
black deakins_forums/

# Lint code
ruff check deakins_forums/
```

## Troubleshooting

### "No results found" when searching
Make sure the index is built:
```bash
python -m deakins_forums.cli build-index
```

### Rate limiting errors (HTTP 429)
Increase the delay:
```bash
export DEAKINS_DELAY_S="5.0"
```

### "Could not extract forum slug from URL"
Make sure the URL format is correct:
- Forum: `https://rogerdeakins.com/forums/forum/<slug>/`
- Topic: `https://rogerdeakins.com/forums/topic/<slug>/`

### Resuming interrupted scrapes
Just run the same command again. The scraper will:
- Check ETags/Last-Modified to skip unchanged pages
- Skip already-downloaded posts
- Continue from where it left off

## Future Enhancements

- [ ] MCP server implementation for AI agent integration
- [ ] Multi-page topic/forum pagination (currently implemented!)
- [ ] Attachment download support
- [ ] Export to other formats (Markdown, SQLite, etc.)
- [ ] Web UI for browsing scraped content
- [ ] Automated incremental update scheduler
- [ ] Better timestamp parsing with timezone support
- [ ] User profile scraping
- [ ] Topic relationship mapping
- [ ] Citation graph analysis

## License

This tool is for personal research and educational purposes only. All forum content remains the property of rogerdeakins.com and its contributors. Commercial use requires explicit permission.
