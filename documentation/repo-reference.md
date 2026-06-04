# Repo Reference

Deep reference for the purefoy knowledge base (ADR-0081 Layer 2 — task reference, not
always-loaded). Repo-wide policy and the command quick-start live in the root `CLAUDE.md`;
the forum-scraper internals live in `deakins_forums/CLAUDE.md`; record schemas in
`documentation/data-model-reference.md`.

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
│   ├── browser-app/        # React/Vite micro-frontend remote (port 3020) — UI via @ojfbot/frame-ui-components (npm ^1.0.1)
│   ├── browser-automation/ # Visual regression testing via browser automation (screenshot capture, CI integration)
│   ├── api/                # Express API over flat JSON + SQLite (port 3021) — includes GET /api/beads (ADR-0016)
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

## Podcast Episode Management

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

### Episode Ingest Design

The `ingest_teamdeakins_downloads.py` script:
- Parses RSS XML to extract episode metadata (title, date, duration, iTunes tags, description)
- Matches downloaded MP3s to RSS entries via URL
- Creates structured episode directories with naming: `S{season}E{episode}__{date}__{guest}__{source_id}/`
- Generates `metadata.json` with comprehensive provenance
- Creates `transcript/` scaffold with `sources.json` and `transcript.txt` (placeholder or fetched)
- Supports Podcasting 2.0 `<podcast:transcript>` URLs and optional Tapesearch fallback

## Testing Notes

- **TypeScript layer**: CI runs TypeScript type-check, test, and codegen drift guard jobs (see `packages/`). Fleet-wide visual regression tests run via the `browser-automation` package (screenshots capture the composed shell, not standalone apps; waits for a Frame sentinel rather than `networkidle`).
- **Python layer**: Manual testing via CLI commands and dry-run flags; no formal Python test suite yet
- Incremental updates can be verified by running scrapes twice and checking for "Not modified" messages
