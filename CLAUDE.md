# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a **Team Deakins Podcast and Forum Knowledge Base** project. It contains:

1. **Podcast Episode Downloader & Ingest**: Scripts to download MP3s from RSS feeds and organize them into structured episode directories with metadata and transcripts.
2. **Forum Scraper (`deakins_forums`)**: A modular, ultra-structured Python package for scraping rogerdeakins.com forums into a searchable JSON-based knowledge base.
3. **TypeScript UI Layer (`packages/`)**: A Module Federation remote (React/Vite micro-frontend on port 3020 + Express API on port 3021) for exploring podcast and forum data locally. UI components are imported from `@ojfbot/frame-ui-components` (DashboardLayout, ChatShell, ThreadSidebar, CondensedChat). Architecture decisions documented in ADR-006 through ADR-009.
4. **Standalone Flask UI (`app.py`)**: A single-file dark-theme knowledge browser at `localhost:5050`, reading directly from `downloads/` and `library/forums/`. Zero dependency on the Module Federation stack — used for local debugging against the raw corpus.
All content is for **personal research and educational purposes only** under fair use principles. Commercial use requires explicit permission from copyright holders.

## Git Data Policy

**What is committed to git:**
- All source code (`deakins_forums/`, `deakins_articles/`, scripts)
- Schema examples with fictional/illustrative content (`documentation/examples-schemas/`)
- Documentation and configuration files

**What is gitignored (on disk only):**
- `library/` — actual scraped content (forum posts, articles, images). This is the canonical data store but needs curation before committing. When ready, commit only the canonical subdirectories: `library/forums/posts/`, `library/forums/topics/`, `library/forums/forums/`, `library/articles/articles/`, `library/articles/films/`
- `library/forums/_site/` — derived runtime state (SQLite index, HTTP cache, coverage tracking). Always regenerable.
- `library/forums/_curated/` — derived curation views. Lives in `analysis/curated/` instead.
- `analysis/` — export outputs and curated views (regenerable from library/)
- `downloads/` — podcast MP3s and episode directories

**Schema examples vs. actual data:** The `documentation/examples-schemas/` directory is the git-committed representation of the data layer. Each file shows the shape of a record type with fictional illustrative content — not real scraped data. See `documentation/examples-schemas/README.md` for field-level documentation.

## Project Structure

```
purefoy/
├── deakins_forums/          # Forum scraper package (structured, MCP-ready)
│   ├── cli.py              # Command-line interface
│   ├── pipeline.py         # High-level scraping orchestration
│   ├── models.py           # Pydantic data models (PostLeaf, TopicLeaf, etc.)
│   ├── parser_bbpress.py   # HTML parsing logic for bbPress forums
│   ├── http_client.py      # Rate-limited HTTP client with ETag support
│   ├── store_json.py       # JSON "leaf" persistence layer
│   ├── index_sqlite.py     # SQLite FTS5 search index
│   ├── normalize.py        # Content extraction (links, quotes, blocks)
│   ├── export.py           # Export utilities (CSV, text, by-author, etc.)
│   ├── coverage.py         # Coverage tracking for incremental scrapes
│   ├── query_tracker.py    # Query provenance/lineage tracking
│   ├── report.py           # Reporting utilities
│   └── config.py           # Settings with env var overrides
├── packages/                # TypeScript UI layer (pnpm workspace)
│   ├── browser-app/        # React/Vite micro-frontend remote (port 3020) — UI via @ojfbot/frame-ui-components
│   ├── api/                # Express API over flat JSON + SQLite (port 3021)
│   └── shared/             # @purefoy/shared — generated OpenAPI schema + API type contracts (incl. GoalManifest, ReviewProgress)
├── app.py                   # Standalone Flask UI — dark-theme knowledge browser (port 5050)
├── download_episodes.py     # Podcast RSS feed downloader (standalone)
├── ingest_teamdeakins_downloads.py  # Episode ingest with metadata & transcripts
├── scrape_forum.py          # Legacy forum scraper (standalone)
├── library/                 # Output directory for scraped data
│   └── forums/             # Forum JSON leafs organized by type
│       ├── posts/          # Individual post JSON files
│       ├── topics/         # Topic index files
│       ├── forums/         # Forum metadata files
│       └── _site/          # Sqlite index, HTTP state, coverage
├── downloads/               # Podcast episode directories (348/348 episodes transcribed)
│   └── S02E176__2026-01-14__guest-name__libsyn_abc123/
│       ├── audio.mp3
│       ├── metadata.json
│       └── transcript/
├── analysis/                # Export output (CSV, text dumps, stats)
├── package.json             # pnpm workspace root
└── pyproject.toml           # Python package metadata
```
```

## Common Commands

### Virtual Environment Setup

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
# OR install as editable package
pip install -e .
```

### Podcast Episode Management

```bash
# Download MP3s from RSS feed
.venv/bin/python3 download_episodes.py

# Organize downloads into episode directories (dry-run)
.venv/bin/python3 ingest_teamdeakins_downloads.py \
  --rss "https://rss.libsyn.com/shows/265448/destinations/2018942.xml" \
  --downloads "./downloads" \
  --dry-run

# Actually ingest with transcript fetching
.venv/bin/python3 ingest_teamdeakins_downloads.py \
  --rss "https://rss.libsyn.com/shows/265448/destinations/2018942.xml" \
  --downloads "./downloads" \
  --fill-transcripts \
  --tapesearch
```

### Forum Scraping (deakins_forums package)

```bash
# Using the CLI entry point (if installed)
deakins-forums scrape-all --max-topics 1000 --build-index
deakins-forums scrape-forum team-deakins --max-pages 20 --build-index
deakins-forums scrape-topic https://rogerdeakins.com/forums/topic/...

# Or using python -m
python -m deakins_forums.cli scrape-forum team-deakins --max-pages 20
python -m deakins_forums.cli build-index
python -m deakins_forums.cli search "lighting techniques" --limit 20
python -m deakins_forums.cli stats

# Export data
python -m deakins_forums.cli export all-text -o analysis/all_posts.txt
python -m deakins_forums.cli export csv -o analysis/posts.csv
python -m deakins_forums.cli export roger-only -o analysis/roger_posts.txt

# Query tracking (provenance)
python -m deakins_forums.cli scrape-forum team-deakins \
  --query-name "Research natural lighting techniques" \
  --querier-role "Cinematographer" \
  --querier-department "Camera" \
  --query-context "TV miniseries prep" \
  --query-intent "Find Team Deakins insights on natural light"

python -m deakins_forums.cli provenance --topic "team-deakins__topic-slug"
python -m deakins_forums.cli coverage --format full
```

### Code Quality (optional-dependencies)

```bash
# Format code
black .

# Lint code
ruff check .

# Run tests (if available)
pytest
```

## Architecture

### Forum Scraper Design

The `deakins_forums` package follows a **composable pipeline architecture**:

1. **HttpClient** (`http_client.py`): Rate-limited HTTP layer with conditional GET (ETag/Last-Modified) support for efficient incremental updates.

2. **Parser** (`parser_bbpress.py`): BeautifulSoup-based HTML extraction for bbPress forum structure. Extracts forums index, forum pages, topic pages, and posts.

3. **Models** (`models.py`): Pydantic models defining the "leaf" JSON structure (v2 schema):
   - `PostLeaf`: Individual post with content, author, timestamps, structured blocks, quotes, links, media, **plus threading fields** (post_type, parent_post_id, parent_type, position)
   - `TopicLeaf`: Topic metadata + post ID index (posts are separate files) **plus reply tree** (recursive nested structure showing conversation hierarchy with thread statistics)
   - `ForumLeaf`: Forum metadata + topic reference list
   - `PostType` enum: Distinguishes "topic" (starter) from "reply" posts
   - All include `Provenance` (source URL, scrape timestamp, HTTP headers) and `Integrity` (content hash for change detection, parser_version tracks schema)

4. **Pipeline** (`pipeline.py`): High-level orchestration gluing fetch → parse → normalize → store. Handles pagination, deduplication, incremental refresh.

5. **Storage** (`store_json.py`): Persists structured JSON "leafs" with deterministic file paths (e.g., `posts/{post_id}.json`). Enables version control and incremental updates.

6. **Index** (`index_sqlite.py`): SQLite FTS5 full-text search index for fast queries across posts. Rebuilt from JSON leafs on demand.

7. **Normalize** (`normalize.py`): Extracts structured content elements (links, media, quotes, content blocks) from raw HTML/text for agent-friendly consumption.

8. **Query Tracking** (`query_tracker.py`): Records provenance of each scrape query (who, why, when, what was accessed) for research auditability.

### Key Design Principles

- **Incremental & Resumable**: HTTP ETag caching, content hashing, and visited URL tracking allow efficient re-scraping
- **Deterministic Paths**: Slug-based file naming enables easy navigation and version control
- **Agent-Friendly**: Ultra-structured JSON with normalized content blocks, quotes, links for downstream AI/MCP tools
- **Provenance-First**: Every leaf includes source URL, scrape timestamp, HTTP headers, content hash
- **Rate-Limited & Respectful**: Configurable delays (default 3s), User-Agent identification, robots.txt compliance

### Episode Ingest Design

The `ingest_teamdeakins_downloads.py` script:
- Parses RSS XML to extract episode metadata (title, date, duration, iTunes tags, description)
- Matches downloaded MP3s to RSS entries via URL
- Creates structured episode directories with naming: `S{season}E{episode}__{date}__{guest}__{source_id}/`
- Generates `metadata.json` with comprehensive provenance
- Creates `transcript/` scaffold with `sources.json` and `transcript.txt` (placeholder or fetched)
- Supports Podcasting 2.0 `<podcast:transcript>` URLs and optional Tapesearch fallback

## Environment Variables

Configure via environment variables (all optional):

```bash
export DEAKINS_BASE_URL="https://rogerdeakins.com"
export DEAKINS_USER_AGENT="Your Custom User Agent"
export DEAKINS_DELAY_S="3.0"          # Seconds between requests
export DEAKINS_TIMEOUT_S="30"         # Request timeout
export DEAKINS_MAX_RETRIES="3"
export DEAKINS_OUT_DIR="./library/forums"
```

## Data Model Reference

### PostLeaf Structure (v2 Schema)

**NEW in v2:** Threading support with parent-child relationships and post types.

```json
{
  "ids": {
    "post_id": "175763",
    "forum_slug": "team-deakins",
    "topic_slug": "lighting-discussion",
    "reply_permalink": "https://...",
    "parent_post_id": "175760",
    "parent_type": "topic",
    "position": 1
  },
  "post_type": "reply",
  "author": {
    "display_name": "Roger A. Deakins",
    "role": "Keymaster"
  },
  "timestamps": {
    "raw": "January 18, 2023 at 3:32 pm #175763",
    "parsed_iso": "2023-01-18T15:32:00",
    "parse_confidence": "medium"
  },
  "content_text": "...",
  "content_html": "...",
  "blocks": [...],
  "quotes": [...],
  "links": [...],
  "media": [...],
  "provenance": {
    "source_url": "...",
    "scraped_at": "2026-01-15T...",
    "http": {"etag": "...", "last_modified": "..."}
  },
  "integrity": {
    "content_hash": "sha256:...",
    "parser_version": "bbpress-v2"
  }
}
```

**Threading Fields:**
- `post_type`: "topic" (starter) or "reply"
- `parent_post_id`: ID of parent post (null for topics)
- `parent_type`: "topic" or "reply" (null for topics)
- `position`: Sequential position in reply list (1-indexed)

### TopicLeaf Structure (v2 Schema)

**NEW in v2:** Hierarchical reply tree with thread statistics.

```json
{
  "topic_url": "https://...",
  "topic_slug": "lighting-discussion",
  "title": "Lighting Discussion",
  "post_ids": ["175760", "175763", "175764"],
  "reply_tree": {
    "post_id": "175760",
    "post_type": "topic",
    "author": "John Doe",
    "timestamp": "2023-01-18T15:00:00",
    "children": [
      {
        "post_id": "175763",
        "post_type": "reply",
        "author": "Roger A. Deakins",
        "timestamp": "2023-01-18T15:32:00",
        "children": []
      },
      {
        "post_id": "175764",
        "post_type": "reply",
        "author": "Jane Smith",
        "timestamp": "2023-01-18T16:00:00",
        "children": []
      }
    ]
  },
  "reply_count": 2,
  "max_depth": 1,
  "provenance": {...},
  "integrity": {
    "content_hash": "sha256:...",
    "parser_version": "bbpress-v2"
  }
}
```

**Reply Tree Fields:**
- `reply_tree`: Recursive nested structure showing conversation flow
- `reply_count`: Total number of replies (excluding topic starter)
- `max_depth`: Maximum nesting depth (0 = no replies, 1 = direct replies only)
- `post_ids`: Flat list for backward compatibility

**Migration Note:** Use `python -m deakins_forums.migrate --rebuild-trees` to rebuild reply trees for existing data.

### Episode metadata.json Structure

```json
{
  "title": "SEASON 2 - EPISODE 176 - Chris Lowe...",
  "guid": "...",
  "pubDate_iso": "2026-01-14",
  "itunes": {
    "season": 2,
    "episode": 176,
    "duration_s": 5400,
    "summary": "..."
  },
  "rss_description": "...",
  "rss_content_encoded": "...",
  "audio": {
    "url": "https://...",
    "mime": "audio/mpeg",
    "size_bytes": 123456789,
    "bitrate_kbps": 128,
    "duration_s": 5400,
    "format": "MP3"
  },
  "provenance": {
    "rss_url": "...",
    "scraped_at": "2026-01-15T...",
    "script_version": "ingest-v2"
  }
}
```

## Testing Notes

- **TypeScript layer**: CI runs TypeScript type-check, test, and codegen drift guard jobs (see `packages/`)
- **Python layer**: Manual testing via CLI commands and dry-run flags; no formal Python test suite yet
- Incremental updates can be verified by running scrapes twice and checking for "Not modified" messages

## Important Fair Use Reminders

- **Personal/educational use only** - no commercial redistribution
- **Keep repository PRIVATE** - scraped forum data is included for research
- Scripts include User-Agent headers identifying research purpose
- Rate limiting is enforced (3s default delay between requests)
- Respect robots.txt and server resources
- All content remains property of original copyright holders
- Contact rogerdeakins.com / Team Deakins for commercial licensing

## Git Repository Notes

This repository includes scraped forum data (`library/forums/`) for private research use:
- Forum content is publicly accessible (not behind authentication)
- Structured JSON format is git-friendly
- Enables incremental updates and change tracking
- **Keep this repository PRIVATE** - do not make public

Audio files (`.mp3`) and episode metadata are excluded via `.gitignore`.
