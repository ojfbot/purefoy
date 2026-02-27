# Schema Examples

This directory is the **git-committed representation** of this project's data layer. It contains illustrative JSON examples showing the shape of each API response / scraped record — not actual scraped content.

## Data Policy

**What lives in git (this directory):**
- Schema examples with fictional/illustrative content
- One example file per record type, showing all fields and their types

**What does NOT live in git (gitignored):**
- `library/` — actual scraped content (forum posts, articles, images)
- `analysis/` — derived exports and curated views
- `downloads/` — podcast MP3s and transcripts
- `*.sqlite`, `*.db` — search indexes (rebuildable from library/)

This separation means the repo is safe to share/open-source: it contains code and schemas but never personal forum content or member-only articles.

---

## Directory Structure

```
examples-schemas/
├── forum/                      # Forum scraper output (deakins_forums)
│   ├── post.json              # PostLeaf v2 — individual post with threading
│   ├── topic.json             # TopicLeaf v2 — topic index with reply tree
│   └── forum.json             # ForumLeaf v1 — forum metadata
├── articles/                   # Articles scraper output (deakins_articles)
│   ├── article.json           # ArticleLeaf v1 — LAL article with images
│   └── film.json              # FilmSectionLeaf v1 — film section index
└── episode/                    # Podcast episode data (ingest_teamdeakins)
    ├── metadata.json          # Episode metadata from RSS
    ├── transcript_sources.json # Transcript source tracking
    └── transcript.txt         # Transcript text format
```

---

## Forum Schemas (bbpress-v2)

### post.json — PostLeaf v2
Individual forum post. Key v2 additions over v1: threading fields.

| Field | Description |
|---|---|
| `ids.post_id` | Unique post identifier |
| `ids.parent_post_id` | ID of parent post (null for topic starters) |
| `ids.parent_type` | `"topic"` or `"reply"` |
| `ids.position` | Sequential position in reply list (1-indexed) |
| `post_type` | `"topic"` (starter post) or `"reply"` |
| `author.role` | `"Keymaster"` = Roger or James; `"Participant"` = community |
| `blocks` | Structured content: `paragraph`, `quote`, `list`, `code` |
| `quotes` | Extracted in-post quotations with attribution |
| `integrity.parser_version` | `"bbpress-v2"` for all current data |

### topic.json — TopicLeaf v2
Topic metadata with full conversation hierarchy.

| Field | Description |
|---|---|
| `post_ids` | Flat list of all post IDs (backward compat) |
| `reply_tree` | Recursive nested structure: root post → `children[]` |
| `reply_count` | Total replies (excludes starter post) |
| `max_depth` | Nesting depth (typically 1 for linear forum threads) |

### forum.json — ForumLeaf v1
Forum-level metadata. Stays at v1 (no threading at this level).

---

## Article Schemas (v1.0.0)

The "Looks at Lighting" (LAL) series requires member authentication. See `deakins_articles/auth_playwright.py`.

### article.json — ArticleLeaf v1
One file per LAL article. Typical coverage: 2–5 articles per film, 8–20 images each.

| Field | Description |
|---|---|
| `metadata.author` | Always `"Roger Deakins"` (these are his authored articles) |
| `metadata.word_count` | Used for reading time estimation |
| `blocks` | Structured content extraction (populated by parser) |
| `images[].local_path` | Relative path within `library/articles/images/` |
| `images[].size_bytes` | For storage budgeting |
| `provenance.http.status_code` | Note: articles use `status_code`, forum posts use `status` |

### film.json — FilmSectionLeaf v1
One file per film in the LAL collection. Index of all articles for that film.

| Field | Description |
|---|---|
| `film_slug` | URL-safe film identifier, used as directory name |
| `article_refs` | Ordered list of articles for this film |
| `total_images` | Aggregate image count across all articles |

---

## Coverage Gaps (as of 2026-02-27)

| Source | Scraped | Available | Coverage |
|---|---|---|---|
| Forum topics | 688 | ~1,277 | ~54% |
| Forum posts | 3,311 | ~3,311+ | ~100% within scraped topics |
| LAL articles | 2 | ~50–100 (estimated) | ~2–4% |
| LAL films | 1 | ~30–40 (estimated) | ~3% |
| Podcast episodes | 345 | 345 | 100% (audio) |
| Podcast transcripts | ~0 | 345 | 0% (needs WhisperX) |

---

## Related Documentation

- `deakins_forums/models.py` — Pydantic model definitions (PostLeaf, TopicLeaf, ForumLeaf)
- `deakins_articles/models.py` — Pydantic model definitions (ArticleLeaf, FilmSectionLeaf)
- `CLAUDE.md` — Architecture and command reference
- `documentation/roadmap/DATA_CLEANING_PLAN.md` — Library curation roadmap
