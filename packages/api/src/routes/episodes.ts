import { Router, type IRouter } from 'express'
import type { Request, Response } from 'express'
import { createReadStream, existsSync } from 'fs'
import type { EpisodeListItem, PaginatedResponse } from '../types.js'
import { episodeCache } from '../services/episode-cache.js'

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
