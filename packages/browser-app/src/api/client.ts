// Typed fetch wrappers for all purefoy-api routes.
import type {
  EpisodeListItem,
  EpisodeDetail,
  ChapterResult,
  ForumTopicSummary,
  ForumPostSummary,
  ForumSearchResult,
  PaginatedResponse,
  EpisodeListParams,
  GoalManifest,
  ReviewProgress,
  SegmentCompact,
} from '../types'

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:3021'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) throw new Error(`purefoy-api ${path} → ${res.status}`)
  return res.json() as Promise<T>
}

export const episodesApi = {
  list: (params: EpisodeListParams): Promise<PaginatedResponse<EpisodeListItem>> => {
    const qs = new URLSearchParams()
    if (params.page)    qs.set('page',   String(params.page))
    if (params.limit)   qs.set('limit',  String(params.limit))
    if (params.topic)   qs.set('topic',  params.topic)
    if (params.film)    qs.set('film',   params.film)
    if (params.season != null) qs.set('season', String(params.season))
    return get<PaginatedResponse<EpisodeListItem>>(`/api/episodes?${qs.toString()}`)
  },

  detail: (slug: string): Promise<EpisodeDetail> =>
    get<EpisodeDetail>(`/api/episodes/${encodeURIComponent(slug)}`),

  chapters: (slug: string): Promise<ChapterResult[]> =>
    get<ChapterResult[]>(`/api/episodes/${encodeURIComponent(slug)}/chapters`),

  // Returns raw Response so TranscriptViewer can stream the NDJSON body
  transcriptStream: (slug: string, signal?: AbortSignal): Promise<Response> =>
    fetch(`${API_BASE}/api/episodes/${encodeURIComponent(slug)}/transcript`, { signal }),

  transcriptGoalStream: (slug: string, signal?: AbortSignal): Promise<Response> =>
    fetch(`${API_BASE}/api/episodes/${encodeURIComponent(slug)}/transcript/goal`, { signal }),

  transcriptGoalMeta: (slug: string): Promise<GoalManifest> =>
    get<GoalManifest>(`/api/episodes/${encodeURIComponent(slug)}/transcript/goal/meta`),

  saveGoal: (slug: string, segments: SegmentCompact[]): Promise<GoalManifest> => {
    return fetch(`${API_BASE}/api/episodes/${encodeURIComponent(slug)}/transcript/goal`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ segments }),
    }).then(r => {
      if (!r.ok) throw new Error(`save goal → ${r.status}`)
      return r.json() as Promise<GoalManifest>
    })
  },

  getReview: (slug: string): Promise<ReviewProgress> =>
    get<ReviewProgress>(`/api/episodes/${encodeURIComponent(slug)}/transcript/review`),

  updateReview: (slug: string, reviewedSegments: number[], totalSegments: number): Promise<ReviewProgress> =>
    fetch(`${API_BASE}/api/episodes/${encodeURIComponent(slug)}/transcript/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reviewed_segments: reviewedSegments, total_segments: totalSegments }),
    }).then(r => r.json() as Promise<ReviewProgress>),
}

export const forumApi = {
  topics: (page = 1, limit = 20): Promise<PaginatedResponse<ForumTopicSummary>> =>
    get<PaginatedResponse<ForumTopicSummary>>(`/api/forum/topics?page=${page}&limit=${limit}`),

  topicDetail: (slug: string): Promise<{ topic: ForumTopicSummary; posts: ForumPostSummary[] }> =>
    get<{ topic: ForumTopicSummary; posts: ForumPostSummary[] }>(`/api/forum/topics/${encodeURIComponent(slug)}`),

  search: (query: string, limit = 20): Promise<ForumSearchResult[]> =>
    get<ForumSearchResult[]>(`/api/forum/search?q=${encodeURIComponent(query)}&limit=${limit}`),
}
