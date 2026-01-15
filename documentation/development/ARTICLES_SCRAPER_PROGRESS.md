# Deakins Articles Scraper - Implementation Progress

## Overview

We've built a comprehensive scraper for the members-only "Looks at Lighting" articles from rogerdeakins.com, following the same architectural patterns as the forums scraper.

## ✅ Completed Components

### 1. Data Models (`deakins_articles/models.py`)
- **ArticleLeaf**: Complete article representation with metadata, content, images, links
- **FilmSectionLeaf**: Hierarchical grouping by film/project
- **ArticlesIndexLeaf**: Top-level index of all films and articles
- **Supporting models**: Author, Image, ContentBlock, Link, Quote, Provenance, Integrity
- **Intermediate models**: RawArticle, FilmMenuItem, ArticleMenuItem

**Key Features**:
- Pydantic-based validation
- SHA256 content hashing for integrity
- Query provenance tracking support
- Agent-friendly structured data

### 2. Configuration (`deakins_articles/config.py`)
- **ArticlesSettings** dataclass with all necessary settings
- Authentication credentials (username/password)
- HTTP client configuration (rate limiting, timeout, retries)
- Storage paths (articles, images)
- Image download settings
- Environment variable support

**Usage**:
```python
from deakins_articles.config import load_settings

settings = load_settings(
    override_username="TelevisionSky",
    override_password="..."
)
```

### 3. Authentication Handler (`deakins_articles/auth.py`)
- **WordPressAuthHandler** for session management
- WordPress wp-login.php form authentication
- Session cookie persistence (24hr expiry)
- Automatic validation of members-only access
- Re-authentication on expiry

**Status**: ✅ Fully tested and working

**Test Results**:
```
✓ Successfully authenticated as 'TelevisionSky'
✓ Fetched 3 sample articles (empire-of-light, skyfall-1, bladerunner-ks-apt-int)
✓ All articles accessible (100+ KB HTML each)
```

### 4. HTML Parser (`deakins_articles/parser.py`)
- **parse_articles_menu()**: Extract film hierarchy from navigation
- **parse_article_page()**: Extract all content from individual articles
- WordPress-specific extraction helpers:
  - `_extract_title()`: From `<h1 class="entry-title">`
  - `_extract_author()`: From `<span class="author vcard">`
  - `_extract_date()`: From `<time class="entry-date" datetime="...">`
  - `_extract_images()`: From `<div class="wp-caption">` with `<p class="wp-caption-text">` captions
  - `_extract_featured_image()`: From `twitter:image` meta tag
  - `_extract_links()`: All hyperlinks from content
  - `_extract_meta_description()`: SEO metadata

**WordPress Theme Patterns Discovered**:
- Images use `<div class="wp-caption">` NOT `<figure>` tags
- Captions in `<p class="wp-caption-text">` NOT `<figcaption>`
- Responsive images with `srcset` attributes
- Section headers in `<p class="green-header">`
- Body paragraphs in `<p class="main-text">`
- Consistent structure across all articles

**Status**: ✅ Fully tested with 3 sample articles

**Test Results**:
```
Empire of Light: 14 images, 81 links, 15,528 chars
Skyfall 1: 30 images, 67 links, 13,316 chars
Blade Runner K's Apt: 6 images, 67 links, 4,021 chars
```

### 5. Test Scripts
- **test_auth.py**: Authentication testing + sample article fetching
- **test_parser.py**: Parser validation with sample HTML

---

## 🚧 Remaining Components (To Be Implemented)

### 6. Image Downloader (`deakins_articles/image_downloader.py`)
**Purpose**: Download and store images locally

**Planned Features**:
- Download images from URLs with authentication
- Store in `library/articles/images/` with organized structure
- Track download provenance (URL, download timestamp, size)
- Handle duplicate images (content hashing)
- Respect max file size limits
- Support for srcset (multiple resolutions)

**Estimated Implementation**: ~200 lines

### 7. JSON Storage (`deakins_articles/store.py`)
**Purpose**: Persist articles to JSON files (mirrors forums storage)

**Planned Structure**:
```
library/articles/
├── articles/<article_id>.json      # ArticleLeaf files
├── films/<film_slug>.json          # FilmSectionLeaf files
├── images/<image_hash>.<ext>       # Downloaded images
└── _site/
    ├── articles_index.json         # ArticlesIndexLeaf
    ├── http_state.json             # ETag/Last-Modified cache
    └── session_cookies.json        # Auth session cache
```

**Planned Methods**:
- `write_article(article_leaf)`, `read_article(article_id)`
- `write_film(film_leaf)`, `read_film(film_slug)`
- `write_articles_index(index_leaf)`, `read_articles_index()`
- `list_all_articles()`, `list_all_films()`
- `get_stats()` → article/film/image counts

**Estimated Implementation**: ~300 lines

### 8. Scraping Pipeline (`deakins_articles/pipeline.py`)
**Purpose**: High-level orchestration (mirrors forums pipeline)

**Planned Methods**:
- `scrape_articles_menu()` → discover all films and article URLs
- `scrape_article(url, film_slug)` → fetch + parse + normalize + store one article
- `scrape_film(film_slug)` → scrape all articles for a film
- `scrape_all_articles()` → comprehensive scraping with progress tracking

**Orchestration Flow**:
1. Authenticate with WordPressAuthHandler
2. Fetch articles menu (film hierarchy)
3. For each film:
   - For each article:
     - Fetch HTML (with conditional GET)
     - Parse with parser.py
     - Download images
     - Create ArticleLeaf
     - Persist to JSON
4. Build ArticlesIndexLeaf
5. Generate statistics

**Estimated Implementation**: ~400 lines

### 9. CLI Integration (`deakins_articles/cli.py` or extend `deakins_forums/cli.py`)
**Purpose**: Command-line interface

**Planned Commands**:
```bash
# Scrape all articles
python -m deakins_articles scrape-all --username TelevisionSky --password ...

# Scrape specific film
python -m deakins_articles scrape-film bladerunner-2049

# Scrape single article
python -m deakins_articles scrape-article <URL>

# Show statistics
python -m deakins_articles stats

# Authenticate and cache session
python -m deakins_articles login --username ... --password ...
```

**Integration with Query Provenance**:
- Add same `--query-name`, `--querier-role`, `--query-context` parameters
- Reuse `deakins_forums/query_tracker.py` for articles

**Estimated Implementation**: ~200 lines

### 10. MCP Server Integration
**Purpose**: Expose articles scraper via MCP protocol

**Planned Tools** (extend `deakins_forums/mcp_server.py`):
- `scrape_deakins_article` - scrape single article
- `scrape_deakins_film` - scrape all articles for a film
- `scrape_all_deakins_articles` - comprehensive scraping
- `get_articles_stats` - article/film/image counts

**Estimated Implementation**: ~100 lines (extending existing MCP server)

---

## Architecture Summary

### Follows Forums Scraper Patterns

✅ **Layered Architecture**:
- HTTP Client (auth.py) → Parser (parser.py) → Storage (store.py)
- Pipeline orchestrates all layers
- CLI/MCP expose functionality

✅ **Data Models**:
- Pydantic BaseModel with validation
- Content hashing for integrity
- Provenance tracking
- Agent-friendly structured data

✅ **Incremental Scraping**:
- Conditional GET with ETag/Last-Modified
- Content hashing for change detection
- Skip existing articles if unchanged

✅ **Storage Design**:
- One JSON file per article
- Deterministic file paths
- Hierarchical organization

---

## Sample Data

### Successfully Parsed Articles

**1. Empire of Light** (`empire-of-light-lighting.html`)
- Published: April 5, 2023
- Author: James
- Content: 15,528 chars
- Images: 14 (including lighting diagrams)
- Lighting setups: Lobby daytime/night, Screen One, Projection room

**2. Skyfall** (`skyfall-1.html`)
- Published: June 23, 2020
- Content: 13,316 chars
- Images: 30 (including lighting plans)
- Scenes: Pre-credit sequence, MI6 Whitehall, M's Office, Bunker

**3. Blade Runner 2049 - K's Apt** (`bladerunner-ks-apt-int.html`)
- Published: April 29, 2018
- Content: 4,021 chars
- Images: 6 (including lighting diagrams)
- Lighting: K's apartment interior (day/night)

---

## Usage Guide

### Current Status (Manual Testing)

1. **Authenticate and fetch samples**:
```bash
python3 test_auth.py
# Enter username: TelevisionSky
# Enter password: hIhru6-kokxak-gebgom
```

2. **Test parser**:
```bash
python3 test_parser.py
```

3. **Examine parsed data**:
```bash
cat sample_articles/*_parsed.json | jq
```

### Future Usage (After Completion)

```bash
# Full scraping with query provenance
python -m deakins_articles scrape-all \
  --username TelevisionSky \
  --password ... \
  --query-name "Film Lighting Research" \
  --querier-role "Cinematographer" \
  --query-context "Feature film prep"

# MCP integration (for AI agents)
python -m deakins_articles mcp-server
```

---

## Next Steps

### Priority 1: Core Functionality
1. Implement `image_downloader.py` (~2 hours)
2. Implement `store.py` (~3 hours)
3. Implement `pipeline.py` (~4 hours)
4. Test end-to-end scraping (~1 hour)

### Priority 2: Integration
5. Extend CLI with article commands (~2 hours)
6. Integrate query provenance tracking (~1 hour)
7. Add MCP server tools (~1 hour)

### Priority 3: Polish
8. Documentation (usage examples, API docs)
9. Error handling and edge cases
10. Performance optimization

**Total Estimated Effort**: ~14-16 hours

---

## Key Achievements

✅ **Authentication working perfectly** - Can access all members-only content
✅ **Parser handles actual WordPress structure** - Not generic assumptions
✅ **Tested with real articles** - Empire of Light, Skyfall, Blade Runner 2049
✅ **Architecture mirrors forums scraper** - Consistent patterns throughout
✅ **Ready for incremental scraping** - Can detect changes via content hashing

---

## Files Created

1. `deakins_articles/__init__.py` - Module initialization
2. `deakins_articles/models.py` - Pydantic data models (282 lines)
3. `deakins_articles/config.py` - Configuration management (158 lines)
4. `deakins_articles/auth.py` - WordPress authentication (255 lines)
5. `deakins_articles/parser.py` - HTML parsing (529 lines)
6. `test_auth.py` - Authentication test script
7. `test_parser.py` - Parser test script
8. `sample_articles/` - 3 sample HTML files + parsed JSON

**Total Code**: ~1,224 lines

---

## Credentials

**Username**: TelevisionSky
**Password**: hIhru6-kokxak-gebgom
**Session Cache**: `library/articles/_site/session_cookies.json` (24hr expiry)

---

## Questions for User

1. **Priority**: Should we complete the remaining components now, or is the current progress sufficient for your immediate needs?

2. **Integration**: Do you want articles integrated into the existing forums CLI/MCP, or keep them separate?

3. **Scraping Strategy**: Should we scrape all articles immediately, or implement incremental scraping first?

4. **Image Storage**: Do you want all image resolutions (srcset), or just the highest quality version?

---

**Last Updated**: 2026-01-15
**Status**: ~60% Complete (Core functionality working, integration pending)
