# deakins_forums — scraper subtree guidance

Path-conditional guidance (ADR-0081 Layer 1): this file loads when you edit the
`deakins_forums/` forum-scraper package. Repo-wide policy lives in the root `CLAUDE.md`;
the leaf/record schemas live in `documentation/data-model-reference.md` (authoritative
source: `deakins_forums/models.py`).

## Forum Scraper Design

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

## Forum Scraping commands

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
