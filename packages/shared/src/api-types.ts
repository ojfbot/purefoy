// Hand-written HTTP API envelope types.
// These cover the Node.js API layer (pagination, query params, HTTP responses)
// and are NOT derived from Python schemas — they represent the API contract.
//
// Python on-disk data shapes live in generated/schema.ts.

import type { PostType } from './generated/schema.js'

// ── Pagination ────────────────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  limit: number
  hasMore: boolean
}

// ── Episode list query params ─────────────────────────────────────────────────

export interface EpisodeListParams {
  page?: number
  limit?: number
  /** Filter by topic tag e.g. "lighting", "camera" */
  topic?: string | null
  /** Filter by film title slug e.g. "blade-runner-2049" */
  film?: string | null
  /** Filter by RSS season number (null = include all seasons) */
  season?: number | null
}

// ── Forum search params ───────────────────────────────────────────────────────

export interface ForumSearchParams {
  /** FTS5 query string */
  q: string
  limit?: number
}

// ── Tool capability manifest (ADR-0007) ───────────────────────────────────────

export interface ToolsManifest {
  name: string
  version: string
  description: string
  capabilities: string[]
  endpoints: Record<string, string>
}

// ── Health ────────────────────────────────────────────────────────────────────

export interface HealthResponse {
  status: 'ok'
  service: string
  timestamp: string
}

// ── API response shapes ───────────────────────────────────────────────────────
// These are HTTP-layer types — computed aggregations served by the Node.js API.
// The API reads Python on-disk data shapes (schema.ts) and returns these.

/** Episode list item — computed from metadata.json + run_manifest.json + extraction_report.json */
export interface EpisodeListItem {
  slug: string
  title: string
  pubDate: string
  season: number | null
  episode: number | null
  duration: string
  hasTranscript: boolean
  canonicalRunId: string | null
  stats: {
    chapters: number
    words: number
    speakers: number
    topics: string[]
    films: string[]
  } | null
}

/** Episode detail — EpisodeListItem + full metadata fields */
export interface EpisodeDetail extends EpisodeListItem {
  descriptionHtml: string
  durationSeconds: number
  imageUrl: string | null
  allRunIds: string[]
}

/** Forum topic summary — flattened from TopicLeaf for list views */
export interface ForumTopicSummary {
  slug: string
  title: string
  topicUrl: string
  replyCount: number
  maxDepth: number
  postIds: string[]
  scrapedAt: string
}

/** Forum post summary — flattened from PostLeaf for topic detail views */
export interface ForumPostSummary {
  postId: string
  topicSlug: string
  postType: PostType
  author: string
  authorRole: string | null
  timestamp: string | null
  contentText: string
  position: number | null
}

/** Forum FTS5 search result */
export interface ForumSearchResult {
  postId: string
  topicSlug: string
  author: string
  timestamp: string | null
  snippet: string
  rank: number
}
