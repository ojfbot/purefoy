import { Router } from 'express'
import type { ToolsManifest } from '../types.js'

export const toolsRouter = Router()

// GET /api/tools — Frame OS capability manifest (ADR-0007)
// The MetaOrchestratorAgent in frame-agent calls this at startup to discover
// what capabilities purefoy exposes for intelligent routing.
toolsRouter.get('/', (_req, res) => {
  const manifest: ToolsManifest = {
    name: 'purefoy',
    version: '0.1.0',
    description: 'Team Deakins cinematography knowledge base — podcast transcripts and forum posts',
    capabilities: [
      'episode_browse',
      'episode_transcript',
      'episode_chapters',
      'forum_browse',
      'forum_search',
    ],
    endpoints: {
      episodes: '/api/episodes',
      episodeDetail: '/api/episodes/:slug',
      episodeChapters: '/api/episodes/:slug/chapters',
      episodeTranscript: '/api/episodes/:slug/transcript',
      forumTopics: '/api/forum/topics',
      forumTopicDetail: '/api/forum/topics/:slug',
      forumSearch: '/api/forum/search',
    },
  }
  res.json(manifest)
})
