# Purefoy: Roger Deakins Cinematography Knowledge Base

A comprehensive research toolkit for building a structured knowledge base from **Team Deakins podcast episodes**, **rogerdeakins.com forum discussions**, and **cinematography articles**.

**Current Status:** Production-ready v2.0 with threading support, 3,075+ forum posts indexed, ready for AI/MCP integration.

> **⚠️ IMPORTANT**: This project is for **personal research and educational purposes only**. All content remains property of its copyright holders. See [Legal & Fair Use](#legal--fair-use) below.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Quick Start](#quick-start)
- [Current Status](#current-status)
- [Documentation](#documentation)
- [Project Structure](#project-structure)
- [Architecture](#architecture)
- [Legal & Fair Use](#legal--fair-use)
- [Contributing](#contributing)

---

## Overview

Purefoy extracts and structures Roger Deakins' cinematography knowledge from multiple sources:

1. **Podcast Episodes** - Team Deakins podcast with transcripts (200+ episodes)
2. **Forum Discussions** - rogerdeakins.com forums (3,075+ posts across 9 forums)
3. **Articles** - Technical articles from rogerdeakins.com (upcoming)

All data is stored in **structured JSON "leafs"** optimized for:
- ✅ Version control (git-friendly)
- ✅ Incremental updates
- ✅ AI/MCP consumption
- ✅ Full-text search
- ✅ Research and analysis

---

## Features

### 🎙️ Podcast Episode Management

- **RSS Feed Parsing** - Extract metadata from Team Deakins feed
- **Automated Downloads** - Download MP3s with organized directories
- **Metadata Extraction** - iTunes tags, duration, guest info, descriptions
- **Transcript Support** - Fetch from Podcasting 2.0 sources and Tapesearch
- **Structured Storage** - `S02E176__2026-01-14__guest-name__id/` format

**Scripts:**
- `download_episodes.py` - Download MP3s from RSS feed
- `ingest_teamdeakins_downloads.py` - Organize into structured directories

---

### 💬 Forum Scraper (v2.0) - `deakins_forums`

The forum scraper is a **production-ready Python package** with advanced features:

#### Core Features
- ✅ **Threading Support** - Parent-child relationships, reply trees, conversation depth
- ✅ **Clean Data Extraction** - Real author names (no stub data), full content
- ✅ **Incremental Updates** - HTTP ETag/Last-Modified caching, content hashing
- ✅ **Full-Text Search** - SQLite FTS5 with porter stemming
- ✅ **Multiple Export Formats** - Text, CSV, by-author, by-topic, statistics
- ✅ **Query Provenance** - Track who scraped what, when, and why
- ✅ **Rate Limiting** - Respectful scraping (3s default delay)
- ✅ **Resumable Scrapes** - Checkpoint-based recovery

#### Data Quality
- **3,075+ posts** successfully scraped
- **691 topics** with full conversation threads
- **490 unique authors** identified
- **9 forums** completely covered
- **100% real author names** (no post ID corruption)

#### Advanced Features
- **Reply Trees** - Nested conversation structures with depth tracking
- **Position Tracking** - Sequential post ordering within topics
- **Content Blocks** - Structured paragraphs, lists, code blocks, quotes
- **Link Extraction** - External URLs with context
- **Media Tracking** - Images, videos, embedded content
- **Statistics** - Corpus-wide metrics and author analytics

**CLI Commands:**
```bash
# Scrape forums
python -m deakins_forums.cli scrape-forum team-deakins --build-index
python -m deakins_forums.cli scrape-all --max-topics 1000

# Search and query
python -m deakins_forums.cli search "natural lighting"
python -m deakins_forums.cli stats

# Export data
python -m deakins_forums.cli export all-text -o analysis/all_posts.txt
python -m deakins_forums.cli export csv -o analysis/posts.csv
python -m deakins_forums.cli export by-author -o analysis/by_author/
python -m deakins_forums.cli export roger-only -o analysis/roger.txt

# Validation and maintenance
python -m deakins_forums.cli validate --verbose
python -m deakins_forums.cli build-index
python -m deakins_forums.cli coverage --format full
```

---

### 📰 Articles Scraper (Beta) - `deakins_articles`

Scrapes technical articles from rogerdeakins.com/articles:

- **Content Extraction** - Parse article HTML to structured JSON
- **Image Handling** - Extract image URLs and captions
- **Metadata** - Dates, categories, tags (when available)
- **Content Blocks** - Paragraphs, headings, lists, code blocks

**Status:** Prototype complete, full integration pending

---

## Quick Start

### Installation

```bash
# Clone repository (private repo assumed)
git clone <repo-url>
cd purefoy

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Or install as editable package
pip install -e .
```

### Basic Usage

#### 1. Scrape Forums

```bash
# Scrape Team Deakins forum (Roger's direct responses)
python -m deakins_forums.cli scrape-forum team-deakins \
  --max-pages 100 \
  --max-topics 1000 \
  --build-index

# Check status
python -m deakins_forums.cli stats
```

#### 2. Search Content

```bash
# Full-text search
python -m deakins_forums.cli search "anamorphic lenses" --limit 10

# Search with context
python -m deakins_forums.cli search "Skyfall" --limit 20
```

#### 3. Export Data

```bash
# Generate all exports
./regenerate_analysis.sh

# Individual exports
python -m deakins_forums.cli export csv -o data/posts.csv
python -m deakins_forums.cli export by-author -o data/by_author/
```

#### 4. Download Podcast Episodes

```bash
# Download MP3s
python download_episodes.py

# Organize and fetch transcripts
python ingest_teamdeakins_downloads.py \
  --rss "https://rss.libsyn.com/shows/265448/destinations/2018942.xml" \
  --downloads "./downloads" \
  --fill-transcripts \
  --tapesearch
```

---

## Current Status

### ✅ Production Ready

| Component | Status | Coverage | Notes |
|-----------|--------|----------|-------|
| **Forum Scraper** | ✅ v2.0 | 3,075 posts, 691 topics | Threading, search, exports working |
| **Search Index** | ✅ Active | FTS5 with 3,075 posts | Fast full-text search |
| **Export Tools** | ✅ Complete | 9 formats | Text, CSV, by-author, by-topic |
| **Data Quality** | ✅ Verified | 100% clean | Real authors, no stubs |

### 🟡 In Progress

| Component | Status | Coverage | Notes |
|-----------|--------|----------|-------|
| **Podcast Transcripts** | 🟡 Beta | 5 test episodes | Tools exist, automation pending |
| **Articles Scraper** | 🟡 Prototype | 3 sample articles | Parser complete, needs integration |

### 📋 Planned

- Full transcript automation (200+ episodes)
- Article scraper integration
- MCP server implementation
- Enhanced analytics and visualization
- Cross-reference linking (forums ↔ podcasts ↔ articles)

See [ROADMAP.md](documentation/roadmap/ROADMAP.md) for detailed plans.

---

## Documentation

### For Users
- **[QUICKSTART.md](QUICKSTART.md)** - Get started in 5 minutes
- **[CLAUDE.md](CLAUDE.md)** - Complete command reference and architecture
- **[Guides](documentation/guides/)** - Feature-specific tutorials

### For Developers
- **[Architecture](documentation/architecture/)** - System design and implementation
- **[Known Issues](documentation/issues/KNOWN_ISSUES.md)** - Bug reports and resolutions
- **[Roadmap](documentation/roadmap/ROADMAP.md)** - Future plans and priorities
- **[Development Sessions](documentation/development/sessions/)** - Historical context

### Examples
- **[Schema Examples](documentation/examples-schemas/)** - Data structure documentation
- **[Article Samples](documentation/examples-articles/)** - Parsed article examples

---

## Project Structure

```
purefoy/
├── README.md                          # This file
├── CLAUDE.md                          # Architecture and command reference
├── QUICKSTART.md                      # Quick start guide
├── pyproject.toml                     # Package configuration
├── requirements.txt                   # Python dependencies
├── .gitignore                         # Git exclusions
│
├── deakins_forums/                    # Forum scraper package (v2)
│   ├── cli.py                         # Command-line interface
│   ├── pipeline.py                    # Scraping orchestration
│   ├── parser_bbpress.py              # HTML parsing
│   ├── models.py                      # Pydantic data schemas
│   ├── store_json.py                  # JSON storage layer
│   ├── index_sqlite.py                # FTS5 search index
│   ├── export.py                      # Export utilities
│   ├── normalize.py                   # Content extraction
│   └── ... (see CLAUDE.md for full package docs)
│
├── deakins_articles/                  # Articles scraper (beta)
│   ├── cli.py
│   ├── parser.py
│   └── models.py
│
├── library/                           # Scraped data (TRACKED)
│   ├── forums/                        # Forum JSON leafs
│   │   ├── posts/                     # 3,075 post files
│   │   ├── topics/                    # 691 topic index files
│   │   ├── forums/                    # 9 forum metadata files
│   │   └── _site/                     # SQLite index, HTTP state
│   └── articles/                      # Article JSON leafs
│
├── documentation/                     # Project documentation
│   ├── guides/                        # User and feature guides
│   ├── architecture/                  # Technical design docs
│   ├── issues/                        # Known issues and bugs
│   ├── roadmap/                       # Future plans
│   ├── development/                   # Development history
│   ├── examples-schemas/              # Data model examples
│   └── examples-articles/             # Sample scraped articles
│
├── scripts/                           # Utility scripts
│   ├── scrape_forum.py                # Legacy scraper (v1)
│   └── tools/                         # Development tools
│
├── download_episodes.py               # Podcast RSS downloader
├── ingest_teamdeakins_downloads.py    # Episode organizer
└── regenerate_analysis.sh             # Regenerate all exports
```

### Excluded from Git (via .gitignore)

```
# Generated/Downloaded Content
downloads/                  # Podcast MP3 files (large, can be re-downloaded)
analysis/                   # Export files (can be regenerated)
teamdeakins_transcripts/    # Extracted transcripts (generated)

# Runtime State
*.sqlite, *.db             # Search index (rebuilds in 5-10s)
http_state.json            # HTTP cache (ephemeral)

# Development
.venv/                     # Virtual environment
__pycache__/               # Python bytecode
.claude/                   # Claude Code working files
.DS_Store                  # macOS metadata
```

**What IS tracked:**
- ✅ All source code (`deakins_forums/`, `deakins_articles/`)
- ✅ Library data (`library/`) - Structured JSON for private repo
- ✅ Documentation and guides
- ✅ Configuration files

---

## Architecture

### Forum Scraper Design

The `deakins_forums` package follows a **composable pipeline architecture**:

```
HTTP Fetch → Parse HTML → Normalize Content → Store JSON → Index FTS5
     ↓            ↓              ↓                ↓            ↓
 ETag Cache  BeautifulSoup  Extract Links    JSON Leafs   SQLite
  Rate Limit   CSS Selectors  Quotes/Media   Content Hash  Search
```

#### Key Components

1. **HttpClient** (`http_client.py`) - Rate-limited HTTP with conditional GET
2. **Parser** (`parser_bbpress.py`) - bbPress HTML extraction
3. **Models** (`models.py`) - Pydantic schemas (PostLeaf, TopicLeaf, ForumLeaf)
4. **Pipeline** (`pipeline.py`) - Orchestrates fetch → parse → normalize → store
5. **Storage** (`store_json.py`) - Deterministic JSON file paths
6. **Index** (`index_sqlite.py`) - SQLite FTS5 for fast search
7. **Normalize** (`normalize.py`) - Extract structured content elements

#### Design Principles

- **Incremental & Resumable** - ETag caching, content hashing, visited URL tracking
- **Deterministic Paths** - Slug-based file naming for easy navigation
- **Agent-Friendly** - Ultra-structured JSON for AI/MCP consumption
- **Provenance-First** - Every leaf includes source URL, timestamp, HTTP headers
- **Rate-Limited** - Respectful scraping (configurable delays)

See [CLAUDE.md](CLAUDE.md) for detailed architecture documentation.

---

## Legal & Fair Use

### Copyright & Usage

**All content remains property of copyright holders:**
- Podcast: Team Deakins, James Deakins, Roger Deakins
- Forums: rogerdeakins.com, individual authors
- Articles: Roger Deakins, contributors

**Permitted Use:**
- ✅ Personal research and education
- ✅ Private knowledge base for learning
- ✅ Academic study of cinematography

**Prohibited Use:**
- ❌ Commercial redistribution
- ❌ Public sharing of scraped data
- ❌ Claiming ownership of content
- ❌ Violating forum Terms of Service

**For commercial use:** Contact copyright holders directly.

---

### Git Repository Privacy

**⚠️ This MUST be a PRIVATE repository**

The project is configured for a private git repository:

- `.gitignore` includes `library/` JSON data (forum content)
- Forum content is publicly accessible but should not be publicly redistributed
- Use for personal/educational research only
- Do not push to public GitHub/GitLab

**If making code public:**
- Exclude `library/` directory entirely
- Include only source code and documentation
- Add clear disclaimers about content copyright

---

### Respectful Scraping

All scrapers implement best practices:

- ✅ **Rate Limiting** - 3 second delays between requests (configurable)
- ✅ **User-Agent** - Clear identification: "Purefoy Research Bot"
- ✅ **Conditional GET** - ETag/Last-Modified headers to minimize bandwidth
- ✅ **robots.txt** - Check and respect (when implemented)
- ✅ **Error Handling** - Graceful failures, no aggressive retries

---

## Contributing

This is a personal research project, but contributions are welcome if you have access.

### Before Contributing

1. Read [CLAUDE.md](CLAUDE.md) for architecture overview
2. Check [Known Issues](documentation/issues/KNOWN_ISSUES.md) for current bugs
3. Review [Roadmap](documentation/roadmap/ROADMAP.md) for planned features

### Development Setup

```bash
# Install in development mode
pip install -e .

# Install development dependencies (optional)
pip install black ruff pytest

# Run formatter
black .

# Run linter
ruff check .
```

### Code Style

- Python 3.9+ type hints
- Pydantic models for data validation
- Docstrings for public APIs
- Follow existing patterns in `deakins_forums/`

---

## Credits

**Project:** Purefoy Knowledge Base
**Purpose:** Personal research and cinematography education
**Content:** Team Deakins Podcast, rogerdeakins.com

**Special Thanks:**
- Roger Deakins, CBE, ASC, BSC - For sharing decades of cinematography wisdom
- James Deakins - For hosting and producing Team Deakins podcast
- rogerdeakins.com community - For thoughtful discussions and insights

---

## License

**Code:** Educational and personal research use only.

**Content:** All scraped content (forums, podcasts, articles) remains property of original copyright holders.

For commercial use or public distribution, contact:
- **Podcast:** Team Deakins / James Deakins
- **Forums/Articles:** rogerdeakins.com

---

## Questions?

- Check [QUICKSTART.md](QUICKSTART.md) for common tasks
- Read [CLAUDE.md](CLAUDE.md) for complete documentation
- Review [Known Issues](documentation/issues/KNOWN_ISSUES.md) for troubleshooting
- See [Roadmap](documentation/roadmap/ROADMAP.md) for future plans

---

**Version:** 2.0.0
**Status:** Production Ready
**Last Updated:** 2026-01-15
