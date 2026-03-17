import type { Express } from 'express'
import { healthRouter } from './health.js'
import { toolsRouter } from './tools.js'
import { episodesRouter } from './episodes.js'
import { forumRouter } from './forum.js'

export function registerRoutes(app: Express): void {
  app.use('/', healthRouter)
  app.use('/api/tools', toolsRouter)
  app.use('/api/episodes', episodesRouter)
  app.use('/api/forum', forumRouter)
}
