import { Router, type IRouter } from 'express'
import type { Request, Response } from 'express'
import type { ForumTopicSummary, PaginatedResponse } from '../types.js'
import { config } from '../config.js'
import { listTopics, getTopicDetail, searchPosts } from '../services/forum-db.js'

export const forumRouter: IRouter = Router()

// ── GET /api/forum/topics ─────────────────────────────────────────────────────
forumRouter.get('/topics', async (_req: Request, res: Response) => {
  const page  = Math.max(1, parseInt(String(_req.query.page ?? '1'), 10) || 1)
  const limit = Math.min(100, Math.max(1, parseInt(String(_req.query.limit ?? '20'), 10) || 20))

  const allTopics = await listTopics(config.forumTopicsDir)

  const total  = allTopics.length
  const offset = (page - 1) * limit
  const paged  = allTopics.slice(offset, offset + limit)

  const response: PaginatedResponse<ForumTopicSummary> = {
    items: paged,
    total,
    page,
    limit,
    hasMore: offset + limit < total,
  }
  res.json(response)
})

// ── GET /api/forum/topics/:slug ───────────────────────────────────────────────
forumRouter.get('/topics/:slug', async (req: Request, res: Response) => {
  const { slug } = req.params
  const result = await getTopicDetail(config.forumTopicsDir, config.forumPostsDir, slug)
  if (!result) {
    res.status(404).json({ error: 'Topic not found', slug })
    return
  }
  res.json(result)
})

// ── GET /api/forum/search ─────────────────────────────────────────────────────
// Query params: q (required), limit (default 20)
forumRouter.get('/search', async (req: Request, res: Response) => {
  const q = String(req.query.q ?? '').trim()
  if (!q) {
    res.status(400).json({ error: 'q param is required' })
    return
  }
  const limit = Math.min(50, Math.max(1, parseInt(String(req.query.limit ?? '20'), 10) || 20))

  try {
    const results = await searchPosts(config.forumIndexDb, q, limit)
    res.json(results)
  } catch (err) {
    console.error('[forum] search error:', err)
    res.status(500).json({ error: 'Search failed' })
  }
})
