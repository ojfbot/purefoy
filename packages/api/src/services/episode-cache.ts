/**
 * Episode list cache — ADR-008.
 *
 * Warms on startup with a full scan of DOWNLOADS_DIR (~870 file reads for 347 episodes).
 * Subsequent list requests are O(1) I/O. fs.watch invalidates individual episodes as
 * new transcription runs complete (new run_manifest.json / extraction_report.json).
 */

import fs from 'fs'
import { readFile, readdir, stat } from 'fs/promises'
import path from 'path'
import type { EpisodeListItem, EpisodeDetail } from '../types.js'
import type { EpisodeMetadata, RunManifest, ExtractionReport } from '@purefoy/shared'

// ── Slug parsing ──────────────────────────────────────────────────────────────

/** Parse S02E182__2026-02-25__martin-campbell__libsyn_abc → season/episode/date */
function parseSlug(slug: string): { season: number | null; episode: number | null; dateFromSlug: string | null } {
  const m = slug.match(/^S(\d+)E(\d+)__(\d{4}-\d{2}-\d{2})/)
  if (!m) return { season: null, episode: null, dateFromSlug: null }
  const seasonRaw = parseInt(m[1], 10)
  return {
    // Season 00 = early unnumbered episodes; season 86 = bonus. Preserve as-is.
    season: seasonRaw,
    episode: parseInt(m[2], 10),
    dateFromSlug: m[3],
  }
}

// ── Per-episode read ──────────────────────────────────────────────────────────

async function readJson<T>(filePath: string): Promise<T | null> {
  try {
    const raw = await readFile(filePath, 'utf8')
    return JSON.parse(raw) as T
  } catch {
    return null
  }
}

async function buildEpisodeItem(slug: string, episodeDir: string): Promise<EpisodeListItem | null> {
  const metaPath = path.join(episodeDir, 'metadata.json')
  const manifestPath = path.join(episodeDir, 'transcript', 'run_manifest.json')

  const meta = await readJson<EpisodeMetadata>(metaPath)
  if (!meta) return null  // skip dirs without metadata.json (incomplete ingests)

  const manifest = await readJson<RunManifest>(manifestPath)
  const canonicalRunId = manifest?.canonical ?? null

  let stats: EpisodeListItem['stats'] = null
  if (canonicalRunId) {
    const reportPath = path.join(episodeDir, 'transcript', 'runs', canonicalRunId, 'extraction_report.json')
    const report = await readJson<ExtractionReport>(reportPath)
    if (report?.success) {
      // Extract topic + film arrays from extraction_report
      // Note: extraction_report doesn't directly list topics/films arrays —
      // those live in transcript.json chapters. For the list view we use counts only.
      stats = {
        chapters: report.chapters_generated,
        words: report.word_count,
        speakers: report.speakers_detected,
        // topics/films arrays require reading full transcript.json (too expensive for list).
        // For filtering, populate lazily from chapters.json instead (see episodesApi.list filter).
        topics: [],
        films: [],
      }
    }
  }

  const slugParsed = parseSlug(slug)

  return {
    slug,
    title: meta.title,
    pubDate: meta.pub_date_iso,
    season: meta.itunes?.season ?? slugParsed.season,
    episode: meta.itunes?.episode ?? slugParsed.episode,
    duration: meta.itunes?.duration ?? '',
    hasTranscript: canonicalRunId !== null,
    canonicalRunId,
    stats,
  }
}

async function buildEpisodeDetail(_slug: string, episodeDir: string, listItem: EpisodeListItem): Promise<EpisodeDetail | null> {
  const metaPath = path.join(episodeDir, 'metadata.json')
  const meta = await readJson<EpisodeMetadata>(metaPath)
  if (!meta) return null

  const manifest = await readJson<RunManifest>(path.join(episodeDir, 'transcript', 'run_manifest.json'))
  const allRunIds = manifest?.runs.map(r => r.run_id) ?? []

  // duration_s is not in metadata.json in the RSS-sourced format —
  // parse itunes.duration "HH:MM:SS" to seconds if available
  let durationSeconds = 0
  if (meta.itunes?.duration) {
    const parts = meta.itunes.duration.split(':').map(Number)
    if (parts.length === 3) durationSeconds = parts[0] * 3600 + parts[1] * 60 + parts[2]
    else if (parts.length === 2) durationSeconds = parts[0] * 60 + parts[1]
  }

  return {
    ...listItem,
    descriptionHtml: meta.description_html ?? '',
    durationSeconds,
    imageUrl: meta.itunes?.image ?? null,
    allRunIds,
  }
}

// ── Cache class ───────────────────────────────────────────────────────────────

export class EpisodeCache {
  private cache = new Map<string, EpisodeListItem>()
  private watcher: fs.FSWatcher | null = null
  private downloadsDir = ''
  async warm(downloadsDir: string): Promise<void> {
    this.downloadsDir = downloadsDir
    const start = Date.now()

    try {
      let entries: string[]
      try {
        entries = await readdir(downloadsDir)
      } catch {
        console.warn(`[episode-cache] downloads dir not found: ${downloadsDir}`)
        return
      }

      const results = await Promise.allSettled(
        entries
          .filter(e => /^S\d+E\d+__/.test(e))  // episode dirs only
          .map(async slug => {
            const item = await buildEpisodeItem(slug, path.join(downloadsDir, slug))
            if (item) this.cache.set(slug, item)
          })
      )

      const failed = results.filter(r => r.status === 'rejected').length
      console.log(
        `[episode-cache] warm complete: ${this.cache.size} episodes in ${Date.now() - start}ms` +
        (failed ? ` (${failed} dirs skipped)` : '')
      )
    } finally {
      // warm complete
    }

    this.startWatcher()
  }

  private startWatcher(): void {
    if (!this.downloadsDir) return
    try {
      this.watcher = fs.watch(this.downloadsDir, { recursive: false }, (_event, filename) => {
        if (!filename || !/^S\d+E\d+__/.test(filename)) return
        // Debounce: a new transcription run writes several files; wait 2s before rescanning
        setTimeout(() => this.rescanEpisode(filename), 2000)
      })
      // Handle async EMFILE / platform errors without crashing the process
      this.watcher.on('error', (err: NodeJS.ErrnoException) => {
        console.warn('[episode-cache] watcher error — cache will not auto-update:', err.code ?? err.message)
        this.watcher?.close()
        this.watcher = null
      })
      console.log('[episode-cache] watching', this.downloadsDir)
    } catch {
      // fs.watch not supported on this filesystem — acceptable for production NFS/Docker
      console.warn('[episode-cache] fs.watch unavailable — cache will not auto-update')
    }
  }

  private async rescanEpisode(slug: string): Promise<void> {
    const episodeDir = path.join(this.downloadsDir, slug)
    try {
      await stat(episodeDir)  // confirm dir still exists (deletions fire events too)
      const item = await buildEpisodeItem(slug, episodeDir)
      if (item) {
        this.cache.set(slug, item)
        console.log(`[episode-cache] refreshed: ${slug}`)
      }
    } catch {
      this.cache.delete(slug)
    }
  }

  getAll(): EpisodeListItem[] {
    return [...this.cache.values()].sort((a, b) => b.pubDate.localeCompare(a.pubDate))
  }

  get(slug: string): EpisodeListItem | undefined {
    return this.cache.get(slug)
  }

  async getDetail(slug: string): Promise<EpisodeDetail | null> {
    const listItem = this.cache.get(slug)
    if (!listItem) return null
    return buildEpisodeDetail(slug, path.join(this.downloadsDir, slug), listItem)
  }

  async getChapters(slug: string): Promise<object[] | null> {
    const listItem = this.cache.get(slug)
    if (!listItem?.canonicalRunId) return null
    const chaptersPath = path.join(
      this.downloadsDir, slug,
      'transcript', 'runs', listItem.canonicalRunId, 'chapters.json'
    )
    return readJson<object[]>(chaptersPath)
  }

  transcriptSegmentsPath(slug: string): string | null {
    const listItem = this.cache.get(slug)
    if (!listItem?.canonicalRunId) return null
    return path.join(
      this.downloadsDir, slug,
      'transcript', 'runs', listItem.canonicalRunId, 'transcript_segments.jsonl'
    )
  }

  get size(): number { return this.cache.size }

  close(): void {
    this.watcher?.close()
  }
}

export const episodeCache = new EpisodeCache()
