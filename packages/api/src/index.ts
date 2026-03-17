import 'dotenv/config'
import express from 'express'
import cors from 'cors'
import { config } from './config.js'
import { registerRoutes } from './routes/index.js'
import { episodeCache } from './services/episode-cache.js'

const app = express()

app.use(cors({
  origin: ['http://localhost:4000', 'http://127.0.0.1:4000', 'http://localhost:3020'],
}))
app.use(express.json())

registerRoutes(app)

// Start listening immediately so K8s/Docker health checks can succeed during cache warm
const server = app.listen(config.port, () => {
  console.log(`[purefoy-api] listening on http://localhost:${config.port}`)
  console.log(`[purefoy-api] downloads: ${config.downloadsDir}`)
  console.log(`[purefoy-api] library:   ${config.libraryDir}`)

  // Warm episode cache in background — requests during warm return empty list (acceptable)
  episodeCache.warm(config.downloadsDir).catch(err => {
    console.error('[purefoy-api] episode cache warm failed:', err)
  })
})

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('[purefoy-api] SIGTERM — shutting down')
  episodeCache.close()
  server.close(() => process.exit(0))
})
process.on('SIGINT', () => {
  episodeCache.close()
  server.close(() => process.exit(0))
})
