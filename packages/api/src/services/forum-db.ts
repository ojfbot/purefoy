/**
 * Forum data service — reads TopicLeaf/PostLeaf JSON files and SQLite FTS5.
 *
 * SQLite schema (see deakins_forums/index_sqlite.py):
 *   posts_fts  — FTS5: post_id UNINDEXED, author, forum_slug, topic_slug, content_text
 *   posts_meta — post_id, author, author_role, forum_slug, topic_slug,
 *                timestamp_iso, reply_permalink, is_housekeeping, content_type
 */

import { readFile, readdir } from 'fs/promises'
import path from 'path'
import type { ForumTopicSummary, ForumPostSummary, ForumSearchResult } from '../types.js'
import type { TopicLeaf, PostLeaf } from '@purefoy/shared'

// better-sqlite3 is a CommonJS module — dynamic import handles the ESM boundary
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let Database: any = null

async function getDatabase() {
  if (!Database) {
    const mod = await import('better-sqlite3')
    Database = mod.default
  }
  return Database
}

// ── JSON helpers ──────────────────────────────────────────────────────────────

async function readJson<T>(filePath: string): Promise<T | null> {
  try {
    return JSON.parse(await readFile(filePath, 'utf8')) as T
  } catch {
    return null
  }
}

// ── Topics ────────────────────────────────────────────────────────────────────

export async function listTopics(topicsDir: string): Promise<ForumTopicSummary[]> {
  let files: string[]
  try {
    files = await readdir(topicsDir)
  } catch {
    return []
  }

  const results = await Promise.allSettled(
    files
      .filter(f => f.endsWith('.json'))
      .map(async f => {
        const slug = f.replace(/\.json$/, '')
        const data = await readJson<TopicLeaf>(path.join(topicsDir, f))
        if (!data) return null
        const summary: ForumTopicSummary = {
          slug: data.topic_slug ?? slug,
          title: data.title ?? slug,
          topicUrl: data.topic_url,
          replyCount: data.reply_count,
          maxDepth: data.max_depth,
          postIds: data.post_ids ?? [],
          scrapedAt: data.provenance.scraped_at,
        }
        return summary
      })
  )

  return results
    .filter((r): r is PromiseFulfilledResult<ForumTopicSummary> =>
      r.status === 'fulfilled' && r.value !== null
    )
    .map(r => r.value)
    .sort((a, b) => b.scrapedAt.localeCompare(a.scrapedAt))
}

export async function getTopicDetail(
  topicsDir: string,
  postsDir: string,
  slug: string
): Promise<{ topic: ForumTopicSummary; posts: ForumPostSummary[] } | null> {
  const data = await readJson<TopicLeaf>(path.join(topicsDir, `${slug}.json`))
  if (!data) return null

  const postIds = data.post_ids ?? []

  const topic: ForumTopicSummary = {
    slug: data.topic_slug ?? slug,
    title: data.title ?? slug,
    topicUrl: data.topic_url,
    replyCount: data.reply_count,
    maxDepth: data.max_depth,
    postIds,
    scrapedAt: data.provenance.scraped_at,
  }

  // Read posts in parallel — missing posts are silently skipped
  const postResults = await Promise.allSettled(
    postIds.map(postId => readJson<PostLeaf>(path.join(postsDir, `${postId}.json`)))
  )

  const posts: ForumPostSummary[] = postResults
    .filter((r): r is PromiseFulfilledResult<PostLeaf> =>
      r.status === 'fulfilled' && r.value !== null
    )
    .map(r => r.value)
    .map(post => ({
      postId: post.ids.post_id,
      topicSlug: post.ids.topic_slug ?? slug,
      postType: post.post_type,
      author: post.author?.display_name ?? 'Unknown',
      authorRole: post.author?.role ?? null,
      timestamp: post.timestamps?.parsed_iso ?? null,
      contentText: post.content_text,
      position: post.ids.position ?? null,
    }))
    .sort((a, b) => (a.position ?? 999) - (b.position ?? 999))

  return { topic, posts }
}

// ── FTS5 search ───────────────────────────────────────────────────────────────

// Module-level DB singleton — opened once on first search, reused across requests
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let _db: any = null

export async function searchPosts(
  dbPath: string,
  query: string,
  limit: number = 20
): Promise<ForumSearchResult[]> {
  if (!query.trim()) return []

  try {
    if (!_db) {
      const Db = await getDatabase()
      _db = new Db(dbPath, { readonly: true, fileMustExist: true })
    }

    // Mirrors Python's search_posts query exactly.
    // snippet() column index 4 = content_text (0-indexed among non-UNINDEXED columns:
    // author=1, forum_slug=2, topic_slug=3, content_text=4).
    // post_id is UNINDEXED so it doesn't count toward snippet column indexing.
    const sql = `
      SELECT
        m.post_id,
        m.author,
        m.topic_slug,
        m.timestamp_iso,
        snippet(posts_fts, 4, '<mark>', '</mark>', '...', 32) AS snippet,
        rank
      FROM posts_fts
      JOIN posts_meta m ON posts_fts.post_id = m.post_id
      WHERE posts_fts MATCH ?
        AND m.is_housekeeping = 0
      ORDER BY rank
      LIMIT ?
    `

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const rows = _db.prepare(sql).all(query, limit) as any[]

    return rows.map(row => ({
      postId: row.post_id as string,
      topicSlug: (row.topic_slug ?? '') as string,
      author: (row.author ?? 'Unknown') as string,
      timestamp: (row.timestamp_iso ?? null) as string | null,
      snippet: (row.snippet ?? '') as string,
      rank: row.rank as number,
    }))
  } catch (err) {
    // DB not built yet (forum not scraped) — return empty rather than 500.
    // better-sqlite3 v11 uses SqliteError with .code, not message-based detection.
    const code = (err as { code?: string }).code
    if (code === 'SQLITE_CANTOPEN' || code === 'SQLITE_ERROR') return []
    if (err instanceof Error && err.message.includes('fileMustExist')) return []
    throw err
  }
}
