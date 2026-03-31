# ADR-010: S3 + CloudFront for Public Data Delivery

**Status:** Accepted — 2026-03-30
**Date:** 2026-03-30
**Deciders:** Jim Green

---

## Context

Purefoy has two Vercel-hosted public apps that need to serve podcast transcript data:

- **tde.jim.software** — Flask standalone UI (`@vercel/python`, READ_ONLY mode)
- **purefoy.jim.software** — React MF remote (calls tde.jim.software API via `VITE_API_URL`)

Both apps are portfolio pieces for active job applications. Currently neither can serve
transcripts because the Flask app reads from `DOWNLOADS_DIR` (local filesystem, 69 GB including
MP3s) which doesn't exist on Vercel. The deploy staging only includes `flask_app.py`,
`templates/`, `static/`, and config files.

The transcript corpus is complete: 348/348 episodes, ~180 MB of structured JSON/JSONL
(metadata, chapters, segments). This data is static — all episodes are fully transcribed
and the corpus changes only when corrections are made.

Beyond transcripts, the project has forum posts, articles, and other data domains that will
need public serving in the future. We need a data delivery strategy that starts with
transcripts and scales to the full corpus.

## Decision

Use **AWS S3 + CloudFront** as the static data CDN for all Purefoy read-only data.

### Architecture

```
┌─────────────────────────────────────┐
│  Local workstation                  │
│  downloads/ (69 GB, MP3s + JSON)    │
│  library/   (forum JSON + SQLite)   │
└──────────────┬──────────────────────┘
               │ scripts/export-transcript-data.py
               │ aws s3 sync
               ▼
┌─────────────────────────────────────┐
│  S3: ojf-static-data               │
│  purefoy/episodes/index.json       │
│  purefoy/episodes/{slug}/meta.json  │
│  purefoy/episodes/{slug}/chapters.json
│  purefoy/episodes/{slug}/transcript.jsonl
│  purefoy/forums/  ← future         │
│  purefoy/articles/ ← future        │
│  frame/  ← future (other apps)     │
└──────────────┬──────────────────────┘
               │ CloudFront distribution
               │ CNAME: data.jim.software (or similar)
               ▼
┌─────────────────────────────────────┐
│  Vercel: tde.jim.software (Flask)   │
│  DATA_CDN_URL env var → CloudFront  │
│  Fetches JSON on request, proxies   │
│  to client with CORS + caching      │
├─────────────────────────────────────┤
│  Vercel: purefoy.jim.software       │
│  (React) → VITE_API_URL →          │
│  tde.jim.software/api/*             │
└─────────────────────────────────────┘
```

### S3 Bucket Structure

```
s3://ojf-static-data/
  purefoy/
    episodes/
      index.json                      ← all EpisodeListItems (pre-computed)
      {episode-slug}/
        meta.json                     ← EpisodeDetail shape (camelCase)
        chapters.json                 ← ChapterResult[] array
        transcript.jsonl              ← SegmentCompact NDJSON
    forums/                           ← future: forum posts/topics
    articles/                         ← future: article data
  frame/                              ← future: other Frame OS apps
```

### Data Flow

1. **Export**: `scripts/export-transcript-data.py` runs locally, walks `downloads/`,
   extracts metadata + chapters + JSONL segments into a flat output directory with
   camelCase keys matching the TypeScript `EpisodeListItem` / `EpisodeDetail` types.

2. **Upload**: `aws s3 sync` pushes the export directory to S3 with appropriate
   content types (`application/json`, `application/x-ndjson`).

3. **Serve**: CloudFront caches and serves with CORS headers. Flask fetches from
   `DATA_CDN_URL` when set, falls back to local `DOWNLOADS_DIR` when not (local dev).

### Flask API Contract Alignment

The Flask app must return responses matching the Express API contract so the React app
works against both:

- `GET /api/episodes` → `PaginatedResponse<EpisodeListItem>` envelope
- All keys camelCase: `pubDate`, `hasTranscript`, `canonicalRunId`, `hasGoal`, `reviewCoverage`
- `GET /api/episodes/<slug>` → `EpisodeDetail` shape
- `GET /api/episodes/<slug>/transcript` → NDJSON streaming (proxied from CDN or filesystem)
- CORS allowing `purefoy.jim.software`, `tde.jim.software`, `frame.jim.software`

### CloudFront Configuration

- **Origin**: S3 bucket (Origin Access Control, not public bucket)
- **Cache behavior**: default TTL 1 hour, max 24 hours (data is static, manual invalidation on re-export)
- **CORS**: `Access-Control-Allow-Origin` for `*.jim.software`
- **Compression**: automatic gzip/brotli for JSON/JSONL
- **Custom domain**: `data.jim.software` or `cdn.jim.software` via Route 53

### Export Script Responsibilities

The export script produces files whose shapes match the TypeScript types exactly:

- `index.json`: array of `EpisodeListItem` objects with computed `stats` (chapters, words, speakers, topics, films)
- `meta.json`: `EpisodeDetail` shape per episode
- `chapters.json`: `ChapterResult[]` — copied as-is from canonical run (already camelCase)
- `transcript.jsonl`: `SegmentCompact` NDJSON — copied as-is from canonical run (already camelCase)

No MP3 audio, speaker embeddings, or goal/review data are exported.

## Alternatives Considered

| Option | Rejected because |
|---|---|
| Bundle data in git + Vercel deploy (~96 MB compressed) | Inflates repo permanently; couples data updates to code deploys; doesn't scale to forums/articles/images |
| Vercel Blob Storage | Vendor lock-in; usage-based pricing less predictable; doesn't serve the broader Frame OS CDN goal |
| Separate VPS (Railway/Fly.io) with filesystem | Monthly cost; operational overhead; overkill for static JSON |
| Pre-generate static JSON as Vercel static assets | No Flask needed for reads, but loses the ability to add server-side logic (pagination, filtering, search) |

## Consequences

**Positive:**
- Data separated from code — update transcripts without redeploying
- CloudFront edge caching gives fast global reads for portfolio reviewers
- Scales to forums, articles, images without architecture changes
- S3 costs negligible for static JSON at portfolio traffic levels (~$0.02/month)
- Local dev unchanged — `DOWNLOADS_DIR` fallback keeps the existing workflow
- Foundation for a shared `ojf-static-data` bucket usable by other Frame OS apps

**Negative / risks:**
- AWS account dependency — need IAM credentials for upload, OAC for CloudFront
- Cold-start latency on Vercel — Flask must fetch from CloudFront on first request (mitigated by CloudFront edge caching + Flask in-memory caching)
- Manual re-export required when corrections are made (acceptable — corrections are rare)
- Two network hops: client → Vercel (Flask) → CloudFront → S3 (mitigated by CloudFront edge proximity)

## Cost Model

At portfolio traffic levels (~100 requests/day):
- **S3 storage**: ~180 MB = ~$0.004/month
- **S3 requests**: ~3,000 GET/month = ~$0.001/month
- **CloudFront**: free tier covers 1 TB/month transfer + 10M requests
- **Total**: effectively free

## Future Expansion

This ADR establishes the pattern for all Purefoy static data:

| Data domain | Status | S3 path | Estimated size |
|---|---|---|---|
| Podcast transcripts | **Phase 1 (this ADR)** | `purefoy/episodes/` | ~180 MB |
| Forum posts + topics | Phase 2 | `purefoy/forums/` | ~15 MB |
| Articles | Phase 3 | `purefoy/articles/` | ~5 MB |
| Speaker profiles | Phase 4 | `purefoy/speakers/` | ~2 MB |

Other Frame OS apps (cv-builder, BlogEngine, TripPlanner) can use the same
`ojf-static-data` bucket under their own prefixes.
