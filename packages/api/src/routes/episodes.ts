import { Router, type IRouter } from 'express'
import type { Request, Response } from 'express'
import { createReadStream, existsSync, readFileSync, writeFileSync, mkdirSync } from 'fs'
import path from 'path'
import type { EpisodeListItem, PaginatedResponse, GoalManifest, ReviewProgress, SegmentCompact } from '../types.js'
import { episodeCache } from '../services/episode-cache.js'

const DOWNLOADS_DIR = process.env.DOWNLOADS_DIR ?? './downloads'

function goalDir(downloadsDir: string, slug: string): string {
  return path.join(downloadsDir, slug, 'transcript', 'goal')
}

export const episodesRouter: IRouter = Router()

// ── GET /api/episodes ─────────────────────────────────────────────────────────
// Query params: page, limit, topic, film, season
episodesRouter.get('/', (req: Request, res: Response) => {
  const page  = Math.max(1, parseInt(String(req.query.page ?? '1'), 10) || 1)
  const limit = Math.min(500, Math.max(1, parseInt(String(req.query.limit ?? '20'), 10) || 20))
  const topicFilter  = (req.query.topic  as string | undefined)?.toLowerCase() ?? null
  const filmFilter   = (req.query.film   as string | undefined)?.toLowerCase() ?? null
  const seasonFilter = req.query.season != null ? parseInt(String(req.query.season), 10) : null

  let items = episodeCache.getAll()

  // Filter
  if (seasonFilter !== null && !isNaN(seasonFilter)) {
    items = items.filter(ep => ep.season === seasonFilter)
  }
  if (topicFilter) {
    items = items.filter(ep =>
      ep.stats?.topics.some(t => t.toLowerCase().includes(topicFilter))
    )
  }
  if (filmFilter) {
    items = items.filter(ep =>
      ep.stats?.films.some(f => f.toLowerCase().includes(filmFilter))
    )
  }

  const total   = items.length
  const offset  = (page - 1) * limit
  const paged   = items.slice(offset, offset + limit)

  const response: PaginatedResponse<EpisodeListItem> = {
    items: paged,
    total,
    page,
    limit,
    hasMore: offset + limit < total,
  }
  res.json(response)
})

// ── GET /api/episodes/:slug ───────────────────────────────────────────────────
episodesRouter.get('/:slug', async (req: Request, res: Response) => {
  const { slug } = req.params
  const detail = await episodeCache.getDetail(slug)
  if (!detail) {
    res.status(404).json({ error: 'Episode not found', slug })
    return
  }
  res.json(detail)
})

// ── GET /api/episodes/:slug/chapters ─────────────────────────────────────────
episodesRouter.get('/:slug/chapters', async (req: Request, res: Response) => {
  const { slug } = req.params
  const listItem = episodeCache.get(slug)
  if (!listItem) {
    res.status(404).json({ error: 'Episode not found', slug })
    return
  }
  if (!listItem.hasTranscript) {
    res.status(404).json({ error: 'No transcript for this episode', slug })
    return
  }
  const chapters = await episodeCache.getChapters(slug)
  if (!chapters) {
    res.status(404).json({ error: 'Chapters not found for canonical run', slug })
    return
  }
  res.json(chapters)
})

// ── GET /api/episodes/:slug/transcript ───────────────────────────────────────
// Streams transcript_segments.jsonl as NDJSON.
// Client reads Response.body line-by-line for incremental rendering.
episodesRouter.get('/:slug/transcript', (req: Request, res: Response) => {
  const { slug } = req.params
  const listItem = episodeCache.get(slug)
  if (!listItem) {
    res.status(404).json({ error: 'Episode not found', slug })
    return
  }
  if (!listItem.hasTranscript) {
    res.status(404).json({ error: 'No transcript for this episode', slug })
    return
  }

  const segmentsPath = episodeCache.transcriptSegmentsPath(slug)
  if (!segmentsPath || !existsSync(segmentsPath)) {
    res.status(404).json({ error: 'Transcript segments file not found', slug })
    return
  }

  res.setHeader('Content-Type', 'application/x-ndjson')
  res.setHeader('Transfer-Encoding', 'chunked')

  const stream = createReadStream(segmentsPath, { encoding: 'utf8' })
  stream.on('error', (err) => {
    // Headers already sent — close the connection
    console.error('[episodes] transcript stream error:', err)
    res.end()
  })
  stream.pipe(res)
})

// ── GET /api/episodes/:slug/transcript/goal ───────────────────────────────────
// Streams goal JSONL (human-corrected segments).
episodesRouter.get('/:slug/transcript/goal', (req: Request, res: Response) => {
  const { slug } = req.params
  const goalPath = path.join(DOWNLOADS_DIR, slug, 'transcript', 'goal', 'transcript_segments_goal.jsonl')
  if (!existsSync(goalPath)) {
    res.status(404).json({ error: 'No goal data for this episode', slug })
    return
  }
  res.setHeader('Content-Type', 'application/x-ndjson')
  res.setHeader('Transfer-Encoding', 'chunked')
  const stream = createReadStream(goalPath, { encoding: 'utf8' })
  stream.on('error', () => res.end())
  stream.pipe(res)
})

// ── GET /api/episodes/:slug/transcript/goal/meta ──────────────────────────────
episodesRouter.get('/:slug/transcript/goal/meta', (req: Request, res: Response) => {
  const { slug } = req.params
  const manifestPath = path.join(goalDir(DOWNLOADS_DIR, slug), 'goal_manifest.json')
  if (!existsSync(manifestPath)) {
    res.status(404).json({ error: 'No goal manifest for this episode', slug })
    return
  }
  try {
    const manifest = JSON.parse(readFileSync(manifestPath, 'utf8')) as GoalManifest
    res.json(manifest)
  } catch {
    res.status(500).json({ error: 'Failed to read goal manifest', slug })
  }
})

// ── POST /api/episodes/:slug/transcript/goal ──────────────────────────────────
// Save goal segments. Diffs vs original to compute correction summary.
episodesRouter.post('/:slug/transcript/goal', (req: Request, res: Response) => {
  const { slug } = req.params
  const body = req.body as { segments?: SegmentCompact[] }
  const segments = body.segments
  if (!Array.isArray(segments) || segments.length === 0) {
    res.status(400).json({ error: 'segments array required' })
    return
  }
  // Validate each segment has required fields
  for (const seg of segments) {
    if (seg.id == null || seg.start == null || seg.end == null || seg.text == null || seg.speaker == null) {
      res.status(400).json({ error: 'Each segment must have id, start, end, text, speaker' })
      return
    }
  }

  const dir = goalDir(DOWNLOADS_DIR, slug)
  try {
    mkdirSync(dir, { recursive: true })
  } catch {
    res.status(500).json({ error: 'Failed to create goal directory' })
    return
  }

  // Write goal JSONL
  const goalPath = path.join(dir, 'transcript_segments_goal.jsonl')
  const lines = segments.map(s => JSON.stringify(s)).join('\n') + '\n'
  try {
    writeFileSync(goalPath, lines, 'utf8')
  } catch {
    res.status(500).json({ error: 'Failed to write goal segments' })
    return
  }

  // Diff vs original to compute correction summary
  let speakerReassignments = 0
  let textEdits = 0
  let totalSegmentsModified = 0
  const listItem = episodeCache.get(slug)
  if (listItem?.canonicalRunId) {
    const origPath = path.join(
      DOWNLOADS_DIR, slug,
      'transcript', 'runs', listItem.canonicalRunId, 'transcript_segments.jsonl'
    )
    if (existsSync(origPath)) {
      try {
        const origLines = readFileSync(origPath, 'utf8').split('\n').filter(l => l.trim())
        const origMap = new Map<number, SegmentCompact>()
        for (const line of origLines) {
          try {
            const seg = JSON.parse(line) as SegmentCompact
            origMap.set(seg.id, seg)
          } catch { /* skip malformed */ }
        }
        for (const seg of segments) {
          const orig = origMap.get(seg.id)
          if (!orig) continue  // new from split — not counted here
          let modified = false
          if (orig.speaker !== seg.speaker) { speakerReassignments++; modified = true }
          if (orig.text !== seg.text) { textEdits++; modified = true }
          if (modified) totalSegmentsModified++
        }
      } catch { /* diff failed — use zeros */ }
    }
  }

  // Build manifest
  const now = new Date().toISOString()
  const existingManifestPath = path.join(dir, 'goal_manifest.json')
  let createdAt = now
  if (existsSync(existingManifestPath)) {
    try {
      const existing = JSON.parse(readFileSync(existingManifestPath, 'utf8')) as GoalManifest
      createdAt = existing.createdAt
    } catch { /* use now */ }
  }

  const manifest: GoalManifest = {
    tag: 'Goal Data',
    sourceRun: listItem?.canonicalRunId ?? '',
    createdAt,
    updatedAt: now,
    segmentCount: segments.length,
    correctionSummary: {
      speakerReassignments,
      textEdits,
      totalSegmentsModified,
    },
  }

  try {
    writeFileSync(existingManifestPath, JSON.stringify(manifest, null, 2), 'utf8')
  } catch {
    res.status(500).json({ error: 'Failed to write goal manifest' })
    return
  }

  res.json(manifest)
})

// ── GET /api/episodes/:slug/transcript/review ─────────────────────────────────
episodesRouter.get('/:slug/transcript/review', (req: Request, res: Response) => {
  const { slug } = req.params
  const reviewPath = path.join(goalDir(DOWNLOADS_DIR, slug), 'review_progress.json')
  if (!existsSync(reviewPath)) {
    const empty: ReviewProgress = {
      exists: false,
      slug,
      reviewedSegments: [],
      totalSegments: 0,
      reviewCoverage: 0,
      firstOpened: '',
      lastReviewed: '',
      sessions: [],
    }
    res.json(empty)
    return
  }
  try {
    const progress = JSON.parse(readFileSync(reviewPath, 'utf8')) as ReviewProgress
    res.json(progress)
  } catch {
    res.status(500).json({ error: 'Failed to read review progress' })
  }
})

// ── POST /api/episodes/:slug/transcript/review ────────────────────────────────
episodesRouter.post('/:slug/transcript/review', (req: Request, res: Response) => {
  const { slug } = req.params
  const body = req.body as { reviewed_segments?: number[]; total_segments?: number }
  const incomingReviewed = Array.isArray(body.reviewed_segments) ? body.reviewed_segments : []
  const totalSegments = typeof body.total_segments === 'number' ? body.total_segments : 0

  const dir = goalDir(DOWNLOADS_DIR, slug)
  try {
    mkdirSync(dir, { recursive: true })
  } catch { /* ignore */ }

  const reviewPath = path.join(dir, 'review_progress.json')
  const now = new Date().toISOString()

  let existing: ReviewProgress = {
    exists: true,
    slug,
    reviewedSegments: [],
    totalSegments,
    reviewCoverage: 0,
    firstOpened: now,
    lastReviewed: now,
    sessions: [],
  }

  if (existsSync(reviewPath)) {
    try {
      existing = JSON.parse(readFileSync(reviewPath, 'utf8')) as ReviewProgress
    } catch { /* start fresh */ }
  }

  // Union reviewed segment arrays
  const reviewedSet = new Set([...existing.reviewedSegments, ...incomingReviewed])
  const reviewedSegments = Array.from(reviewedSet).sort((a, b) => a - b)
  const effectiveTotal = totalSegments || existing.totalSegments || 1
  const reviewCoverage = reviewedSegments.length / effectiveTotal

  const sessionReviewed = incomingReviewed.filter(id => !existing.reviewedSegments.includes(id)).length

  const updated: ReviewProgress = {
    exists: true,
    slug,
    reviewedSegments,
    totalSegments: effectiveTotal,
    reviewCoverage,
    firstOpened: existing.firstOpened || now,
    lastReviewed: now,
    sessions: [
      ...existing.sessions,
      {
        timestamp: now,
        segmentsReviewedThisSession: sessionReviewed,
        cumulativeReviewed: reviewedSegments.length,
      },
    ],
  }

  try {
    writeFileSync(reviewPath, JSON.stringify(updated, null, 2), 'utf8')
  } catch {
    res.status(500).json({ error: 'Failed to write review progress' })
    return
  }

  res.json(updated)
})
