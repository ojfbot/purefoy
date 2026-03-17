// All types for the API layer come from @purefoy/shared.
// @purefoy/shared is the single source of truth for both on-disk data shapes
// (generated from Python) and HTTP API response shapes (hand-written).
export type {
  // HTTP envelopes
  PaginatedResponse,
  EpisodeListParams,
  ForumSearchParams,
  ToolsManifest,
  HealthResponse,
  // API response shapes
  EpisodeListItem,
  EpisodeDetail,
  ForumTopicSummary,
  ForumPostSummary,
  ForumSearchResult,
  // Python on-disk data shapes (generated from Pydantic/dataclasses)
  PostLeaf,
  TopicLeaf,
  PostType,
  PostIds,
  Author,
  Timestamps,
  EpisodeMetadata,
  ExtractionReport,
  RunManifest,
  RunManifestEntry,
  ChapterResult,
  SegmentResult,
  SegmentCompact,
  WordTimestamp,
} from '@purefoy/shared'
