# ADR-008: Episode List Caching Strategy

**Status:** Accepted — to be implemented
**Date:** 2026-03-16
**Deciders:** Jim Green

---

## Context

The `GET /api/episodes` route must enumerate all episode directories in `downloads/`,
then for each episode read up to 3 JSON files:

1. `metadata.json` — title, date, season, episode, duration
2. `transcript/run_manifest.json` — canonical run ID, has-transcript flag
3. `transcript/runs/{canonical}/extraction_report.json` — stats (chapters, words, speakers, topics, films)

With 290 transcribed episodes (347 total), this is **~870–1,041 synchronous file reads per
list request** if done naively. At ~0.1ms per read on local NVMe: ~100ms per request — marginal
but unacceptable as the corpus grows to 347+.

## Decision

**Startup warm cache with `fs.watch` invalidation**

On server startup, `packages/api/src/services/episode-cache.ts` performs a one-time full scan,
builds an in-memory `Map<slug, EpisodeListItem>`, and returns it sorted. Subsequent `GET /api/episodes`
reads from the cache (0ms I/O).

Cache invalidation:
- `fs.watch(downloadsDir, { recursive: true })` fires on new episode dirs, new run manifests, or
  new extraction reports → re-scans only the affected episode directory (partial refresh).
- Full rescan available via `POST /api/admin/refresh-cache` (internal, not exposed to shell).

Cache warm time estimate:
- 347 directories × 3 reads = ~1,041 file reads
- At ~0.5ms each (includes JSON.parse): ~520ms at startup
- Cache stays warm for the process lifetime

```
startup → full_scan() → Map<slug, EpisodeListItem>
                             ↓
              GET /api/episodes → filter + sort from Map (0ms I/O)
              GET /api/episodes/:slug → Map.get(slug) (0ms I/O)
                             ↑
              fs.watch event → partial_rescan(affectedSlug)
```

## Alternatives considered

| Option | Rejected because |
|---|---|
| Per-request filesystem scan | ~870 file ops per request — degrades as corpus grows; blocking I/O on Express thread |
| SQLite manifest index | Requires a write step when Python pipeline runs; adds write complexity to a read-only architecture; the FTS5 index already exists for forum search — consistent to keep episodes simpler |
| Redis cache | External dependency for a local-first personal tool |
| No cache (read-through) | Acceptable for now at 347 episodes, but will hit Node.js event loop budget on slower storage |
| `chokidar` watcher | More features than needed; `core-reader` uses it — keep `fs.watch` for simplicity |

## Consequences

**Positive:**
- `GET /api/episodes` is O(1) I/O after warmup
- Works correctly after `ingest_teamdeakins_downloads.py` adds new episodes (watcher fires)
- No external dependencies

**Negative:**
- ~500ms startup delay (acceptable — API is long-running)
- Memory: 347 episodes × ~1KB = ~350KB — negligible
- Watcher not supported on all filesystems (NFS, Docker volumes) — fall back to full rescan on interval if `fs.watch` unavailable

## Implementation notes

```typescript
// packages/api/src/services/episode-cache.ts
// TODO: implement — see this ADR for spec
export class EpisodeCache {
  private cache = new Map<string, EpisodeListItem>()
  private watcher: FSWatcher | null = null

  async warm(downloadsDir: string): Promise<void> { /* full scan */ }
  private async rescanEpisode(slug: string): Promise<void> { /* partial refresh */ }
  getAll(): EpisodeListItem[] { return [...this.cache.values()].sort(...) }
  get(slug: string): EpisodeListItem | undefined { return this.cache.get(slug) }
}
```
