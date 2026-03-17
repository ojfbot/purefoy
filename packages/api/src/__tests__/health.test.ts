import { describe, it, expect, beforeAll, afterAll } from 'vitest'
import express from 'express'
import type { Server } from 'http'
import { healthRouter } from '../routes/health.js'
import { toolsRouter } from '../routes/tools.js'

let server: Server
let base: string

beforeAll(async () => {
  const app = express()
  app.use('/', healthRouter)
  app.use('/api/tools', toolsRouter)
  await new Promise<void>(resolve => {
    server = app.listen(0, () => {
      const addr = server.address()
      base = `http://127.0.0.1:${typeof addr === 'object' && addr ? addr.port : 0}`
      resolve()
    })
  })
})

afterAll(() => server.close())

describe('GET /health', () => {
  it('returns 200 with status: ok', async () => {
    const res = await fetch(`${base}/health`)
    expect(res.status).toBe(200)
    const body = await res.json() as Record<string, unknown>
    expect(body.status).toBe('ok')
  })

  it('returns service: purefoy-api', async () => {
    const res = await fetch(`${base}/health`)
    const body = await res.json() as Record<string, unknown>
    expect(body.service).toBe('purefoy-api')
  })

  it('returns ISO timestamp', async () => {
    const res = await fetch(`${base}/health`)
    const body = await res.json() as Record<string, unknown>
    expect(typeof body.timestamp).toBe('string')
    expect(() => new Date(body.timestamp as string)).not.toThrow()
  })
})

describe('GET /api/tools', () => {
  it('returns ToolsManifest with all expected capabilities', async () => {
    const res = await fetch(`${base}/api/tools`)
    expect(res.status).toBe(200)
    const body = await res.json() as Record<string, unknown>
    expect(body.name).toBe('purefoy')
    expect(Array.isArray(body.capabilities)).toBe(true)
    const caps = body.capabilities as string[]
    expect(caps).toContain('episode_browse')
    expect(caps).toContain('forum_search')
  })

  it('endpoints map includes all route paths', async () => {
    const res = await fetch(`${base}/api/tools`)
    const body = await res.json() as Record<string, unknown>
    const endpoints = body.endpoints as Record<string, string>
    expect(endpoints.episodes).toBeDefined()
    expect(endpoints.forumSearch).toBeDefined()
  })
})
