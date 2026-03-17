import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// SCAFFOLD: All paths resolved from env vars so the API works both locally
// (where downloads/ and library/ sit at repo root) and in any deployment context.
// Default: resolve relative to the package directory (packages/api → ../../ = repo root)
const PKG_ROOT = path.resolve(__dirname, '..') // packages/api/
const REPO_ROOT = path.resolve(PKG_ROOT, '..', '..') // purefoy/

export const config = {
  port: parseInt(process.env.PORT ?? '3021', 10),
  // SCAFFOLD: needs real value in .env.local
  downloadsDir: process.env.DOWNLOADS_DIR ?? path.resolve(REPO_ROOT, 'downloads'),
  libraryDir: process.env.LIBRARY_DIR ?? path.resolve(REPO_ROOT, 'library'),

  // Derived paths — do not override individually
  get forumsDir() { return path.resolve(this.libraryDir, 'forums') },
  get forumPostsDir() { return path.resolve(this.libraryDir, 'forums', 'posts') },
  get forumTopicsDir() { return path.resolve(this.libraryDir, 'forums', 'topics') },
  get forumIndexDb() { return path.resolve(this.libraryDir, 'forums', '_site', 'index.db') },
} as const
