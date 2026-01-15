# Deakins Articles Scraper

Complete scraper for Roger Deakins' "Looks at Lighting" members-only articles from rogerdeakins.com.

## Overview

This scraper extracts detailed lighting analysis articles from the members-only section of Roger Deakins' website, including:
- Full article content (HTML + text)
- Lighting diagrams and images
- Article metadata (author, dates, descriptions)
- Film/project hierarchical organization
- Query provenance tracking (compatible with forums scraper)

## Features

✅ **WordPress Authentication** - Handles members-only content with session caching
✅ **Complete Content Extraction** - Title, author, dates, content, images with captions
✅ **Image Downloading** - Downloads and stores images locally with deduplication
✅ **Hierarchical Organization** - Films → Articles with references
✅ **Incremental Scraping** - Skips unchanged articles via content hashing
✅ **Rate Limiting** - Respectful delays between requests
✅ **Provenance Tracking** - Records when/how each article was scraped
✅ **CLI Interface** - Easy command-line usage
✅ **MCP Compatible** - Ready for AI agent integration (future)

## Architecture

Mirrors the `deakins_forums` scraper architecture:

```
deakins_articles/
├── __init__.py          - Module initialization
├── models.py            - Pydantic data models (ArticleLeaf, FilmSectionLeaf, etc.)
├── config.py            - Configuration with environment variable support
├── auth.py              - WordPress authentication handler
├── parser.py            - HTML parsing for WordPress theme
├── image_downloader.py  - Image downloading with deduplication
├── store.py             - JSON storage system
├── pipeline.py          - High-level orchestration
├── cli.py               - Command-line interface
└── __main__.py          - Makes module runnable
```

## Installation

### Prerequisites

```bash
pip3 install pydantic beautifulsoup4 requests
```

### Configuration

Set environment variables (optional):

```bash
export DEAKINS_ARTICLES_USERNAME="your_username"
export DEAKINS_ARTICLES_PASSWORD="your_password"
export DEAKINS_ARTICLES_OUT_DIR="./library/articles"
export DEAKINS_ARTICLES_DOWNLOAD_IMAGES="true"
```

Or pass credentials via CLI arguments.

## Usage

### 1. List Available Films

Discover all films and articles without scraping:

```bash
python3 -m deakins_articles list-films \
  --username TelevisionSky \
  --password your_password
```

**Output**:
```
======================================================================
DISCOVERED FILMS AND ARTICLES
======================================================================

1. Blade Runner 2049
   Slug: bladerunner-2049
   Articles: 17

2. Skyfall
   Slug: skyfall
   Articles: 5

3. No Country for Old Men
   Slug: no-country-for-old-men
   Articles: 6

... (19 films total, 84 articles)
```

### 2. Scrape Single Article

Test scraping one article:

```bash
python3 -m deakins_articles scrape-article \
  https://www.rogerdeakins.com/empire-of-light-lighting/ \
  --username TelevisionSky \
  --password your_password
```

**Output**:
```
✓ Loaded cached session for 'TelevisionSky'

  Scraping: https://www.rogerdeakins.com/empire-of-light-lighting/
    Title: Roger Deakins - Looking at Lighting - Empire of Light
    Film: empire-of-light
    Images: 14
    Downloading 14 images...
    ✓ Saved to: articles/empire-of-light-lighting.json

✓ Article saved to: library/articles/articles/empire-of-light-lighting.json
```

### 3. Scrape Entire Film

Scrape all articles for a specific film:

```bash
python3 -m deakins_articles scrape-film bladerunner-2049 \
  --username TelevisionSky \
  --password your_password
```

This will scrape all 17 Blade Runner 2049 articles.

### 4. Scrape All Articles

Scrape the complete collection (84 articles):

```bash
python3 -m deakins_articles scrape-all \
  --username TelevisionSky \
  --password your_password
```

**Limit scraping**:
```bash
# Scrape first 5 films only
python3 -m deakins_articles scrape-all \
  --max-films 5 \
  --username ... --password ...

# Scrape first 3 articles per film
python3 -m deakins_articles scrape-all \
  --max-articles 3 \
  --username ... --password ...
```

### 5. View Statistics

```bash
python3 -m deakins_articles stats
```

**Output**:
```
======================================================================
ARTICLES STORAGE STATISTICS
======================================================================
Articles:      84
Films:         19
Images:        450
Storage:       5.2 MB
======================================================================

Image Storage:
  Files:   450
  Size:    12.3 MB
```

### 6. Cache Authentication Session

Cache session for 24 hours to avoid re-authenticating:

```bash
python3 -m deakins_articles login \
  --username TelevisionSky \
  --password your_password
```

Session cached to: `library/articles/_site/session_cookies.json`

## Storage Structure

```
library/articles/
├── articles/                       # Individual article JSON files
│   ├── empire-of-light-lighting.json
│   ├── skyfall-1.json
│   ├── bladerunner-ks-apt-int.json
│   └── ... (84 total)
├── films/                          # Film section groupings
│   ├── bladerunner-2049.json
│   ├── skyfall.json
│   └── ... (19 total)
├── images/                         # Downloaded images
│   ├── a3f2d8e1-4c2b.jpg
│   ├── b7e9f1a3-8d5c.jpg
│   └── ... (450+ images)
└── _site/                          # Metadata
    ├── articles_index.json         # Complete index
    ├── http_state.json             # ETag/Last-Modified cache
    └── session_cookies.json        # Auth session (24hr expiry)
```

## Data Models

### ArticleLeaf

Complete article representation:

```json
{
  "ids": {
    "article_id": "empire-of-light-lighting",
    "film_slug": "empire-of-light",
    "article_slug": "empire-of-light-lighting",
    "article_url": "https://www.rogerdeakins.com/empire-of-light-lighting/"
  },
  "metadata": {
    "title": "Roger Deakins - Looking at Lighting - Empire of Light",
    "author": {"display_name": "James"},
    "published_date": "2023-04-05T07:44:58-07:00",
    "word_count": 3882,
    "featured_image": {"src_url": "..."}
  },
  "content_html": "<div class='entry-content'>...</div>",
  "content_text": "Full plain text content...",
  "images": [
    {
      "src_url": "https://www.rogerdeakins.com/wp-content/uploads/2023/04/Web-widerFireworks.jpg",
      "local_path": "images/a3f2d8e1-4c2b.jpg",
      "caption": "\"Empire of Light\" Searchlight Pictures",
      "width": 600,
      "height": 338,
      "size_bytes": 45123
    }
  ],
  "links": [...],
  "provenance": {
    "source_url": "https://www.rogerdeakins.com/empire-of-light-lighting/",
    "scraped_at": "2026-01-15T05:12:34.567890",
    "http": {"status_code": 200, "etag": "..."}
  },
  "integrity": {
    "content_hash": "a3f2d8e1bc4f",
    "parser_version": "1.0.0"
  }
}
```

### FilmSectionLeaf

Film with article references:

```json
{
  "film_id": "bladerunner-2049",
  "film_slug": "bladerunner-2049",
  "film_title": "Bladerunner 2049",
  "article_refs": [
    {
      "article_id": "bladerunner-ks-apt-int",
      "article_url": "https://www.rogerdeakins.com/bladerunner-ks-apt-int/",
      "title": "Bladerunner 2049 - K's Apt Int"
    }
  ],
  "article_count": 17,
  "total_images": 156,
  "scraped_at": "2026-01-15T05:30:00.000000"
}
```

## Complete Collection Overview

As of 2026-01-15, the "Looks at Lighting" collection contains:

| Film | Articles | Notable Scenes |
|------|----------|----------------|
| **Blade Runner 2049** | 17 | K's Apt, Vegas Casino, Wallace's Office, Orphanage |
| **Hail Caesar** | 12 | Calvary, Eddie's Office, Merrily We Dance |
| **No Country for Old Men** | 6 | The Basin at Night, Border, Motel, Hospital |
| **Skyfall** | 5 | Pre-Credit Seq, MI6, Skyfall Lodge |
| **Hudsucker Proxy** | 6 | Boardroom, Clock Room, Mailroom |
| **Sicario** | 4 | Tunnel, Track House, Immigrant Warehouse |
| **The Man Who Wasn't There** | 4 | Barber Shop, Bingo, Bank |
| **Unbroken** | 3 | Plane, Omari Night, Ship Hold |
| **The Goldfinch** | 3 | Amsterdam, NY Shoot (Parts 1 & 2) |
| **Jesse James** | 3 | Blue Cut Train, Ballroom, Ed Miller's Death |
| **Barton Fink** | 2 | Hotel Lobby, Various Scenes |
| **Kundun** | 2 | Potala locations |
| **Others** | 17 | Various films (1984, Prisoners, True Grit, etc.) |

**Total**: 84 articles across 19 films/projects

## Advanced Usage

### Python API

Use the pipeline directly in Python:

```python
from deakins_articles.config import load_settings
from deakins_articles.pipeline import build_pipeline

# Load configuration
settings = load_settings(
    override_username="TelevisionSky",
    override_password="your_password",
)

# Build pipeline (authenticates automatically)
pipeline = build_pipeline(settings)

# Scrape single article
article = pipeline.scrape_article(
    article_url="https://www.rogerdeakins.com/skyfall-1/",
    film_slug="skyfall",
)

# Scrape entire film
film_section = pipeline.scrape_film(
    film_slug="skyfall",
    film_title="Skyfall",
    articles=[...],  # List of article dicts
)

# Scrape all
index = pipeline.scrape_all_articles()
```

### Access Stored Data

```python
from deakins_articles.store import ArticleJsonStore
from pathlib import Path

store = ArticleJsonStore(Path("library/articles"))

# Read article
article = store.read_article("empire-of-light-lighting")
print(article.metadata.title)
print(f"Images: {len(article.images)}")

# Find articles by film
articles = store.find_articles_by_film("bladerunner-2049")
print(f"Found {len(articles)} Blade Runner articles")

# Search
matches = store.search_articles("lighting plan")
print(f"Found {len(matches)} articles mentioning 'lighting plan'")

# Statistics
stats = store.get_stats()
print(f"Total articles: {stats['articles']}")
```

## Testing

### Test Authentication

```bash
python3 test_auth.py
# Prompts for credentials, fetches 3 sample articles
```

### Test Parser

```bash
python3 test_parser.py
# Parses sample HTML files, validates extraction
```

### Demo Scraper

```bash
python3 demo_articles_scraper.py
# Scrapes 3 demo films (5 articles total)
```

## Troubleshooting

### Authentication Issues

**Problem**: "Authentication failed"

**Solutions**:
- Verify credentials are correct
- Clear cached session: `rm library/articles/_site/session_cookies.json`
- Try manual login test: `python3 -m deakins_articles login --username ... --password ...`

### Missing Images

**Problem**: Images not downloading

**Solutions**:
- Check `DEAKINS_ARTICLES_DOWNLOAD_IMAGES=true`
- Verify image directory exists and is writable
- Check network connectivity

### Rate Limiting

**Problem**: Getting 429 errors

**Solutions**:
- Increase delay: `export DEAKINS_ARTICLES_DELAY_S=5.0`
- Scrape smaller batches
- Use cached session to avoid re-authentication overhead

## Query Provenance Integration

The articles scraper is designed to integrate with the forums query provenance system:

```bash
# Future: Track article research queries
python3 -m deakins_articles scrape-film bladerunner-2049 \
  --query-name "Blade Runner Lighting Research" \
  --querier-role "Cinematographer" \
  --query-context "Feature film prep" \
  --username ... --password ...
```

This will log which queries accessed which articles, enabling organizational intelligence tracking across both forums and articles.

## Performance

**Typical Scraping Times**:
- Single article: ~5-10 seconds (including images)
- Small film (1-3 articles): ~30 seconds
- Medium film (5-10 articles): ~2-3 minutes
- Large film (15-20 articles): ~5-7 minutes
- **Complete collection (84 articles)**: ~30-40 minutes

**Storage Requirements**:
- Articles JSON: ~5-10 MB
- Images: ~10-20 MB (varies by article)
- Total: ~15-30 MB for complete collection

## Future Enhancements

- [ ] Query provenance integration (like forums)
- [ ] MCP server tools for AI agents
- [ ] SQLite FTS5 search index
- [ ] Content block extraction (structured paragraphs/lists)
- [ ] Quote extraction with attribution
- [ ] Export to Markdown/PDF
- [ ] Automated update detection
- [ ] Related articles discovery

## Credits

- **Architecture**: Mirrors `deakins_forums` scraper by design
- **Authentication**: WordPress wp-login.php form handling
- **Parsing**: BeautifulSoup for HTML extraction
- **Storage**: Pydantic models with JSON persistence
- **Author**: Built for comprehensive lighting research archives

## License

Educational/Research use. Respect rogerdeakins.com terms of service.

---

**Documentation Version**: 1.0.0
**Last Updated**: 2026-01-15
