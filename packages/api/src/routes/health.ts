import { Router, type IRouter } from 'express'

export const healthRouter: IRouter = Router()

healthRouter.get('/health', (_req, res) => {
  res.json({ status: 'ok', service: 'purefoy-api', timestamp: new Date().toISOString() })
})
