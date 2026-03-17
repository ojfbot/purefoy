// AUTO-GENERATED — do not edit manually.
// Source: scripts/generate_schema.py → openapi.json → openapi-typescript
// Regenerate: pnpm codegen
//
// This file mirrors the Python Pydantic models in deakins_forums/models.py
// and the dataclasses in scripts/tools/transcribe_episodes.py.
// Run `pnpm codegen` after any Python model change to keep these in sync.

// ── Forum domain (from deakins_forums/models.py) ─────────────────────────────

export type PostType = 'topic' | 'reply' | 'article'

export interface HttpProvenance {
  url: string
  status: number | null
  etag: string | null
  last_modified: string | null
}

export interface Provenance {
  source_url: string
  scraped_at: string
  http: HttpProvenance | null
}

export interface Integrity {
  content_hash: string
  parser_version: string
}

export interface Link {
  href: string
  text: string | null
  kind: 'internal' | 'external'
}

export interface Media {
  src: string
  alt: string | null
  kind: 'image' | 'attachment'
  local_path: string | null
}

export interface Quote {
  text: string
  attributed_to: string | null
}

export interface ContentBlock {
  type: 'paragraph' | 'quote' | 'list' | 'code' | 'heading' | 'unknown'
  text: string
}

export interface PostIds {
  post_id: string
  forum_slug: string | null
  topic_slug: string | null
  reply_permalink: string | null
  parent_post_id: string | null
  parent_type: PostType | null
  position: number | null
  wp_post_id: string | null
}

export interface Author {
  display_name: string
  role: string | null
}

export interface Timestamps {
  raw: string | null
  parsed_iso: string | null
  parse_confidence: 'high' | 'medium' | 'low' | 'none'
}

/** PostLeaf v2 — on-disk JSON at library/forums/posts/{post_id}.json */
export interface PostLeaf {
  ids: PostIds
  post_type: PostType
  author: Author | null
  timestamps: Timestamps
  content_text: string
  content_html: string | null
  blocks: ContentBlock[]
  quotes: Quote[]
  links: Link[]
  media: Media[]
  title: string | null
  description: string | null
  featured_image: string | null
  series: string | null
  provenance: Provenance
  integrity: Integrity
}

export interface ReplyTreeNode {
  post_id: string
  post_type: PostType
  author: string
  timestamp: string | null
  children: ReplyTreeNode[]
}

/** TopicLeaf v2 — on-disk JSON at library/forums/topics/{slug}.json */
export interface TopicLeaf {
  topic_url: string
  forum_slug: string | null
  topic_slug: string | null
  title: string | null
  breadcrumb: string[]
  tags: string[]
  post_ids: string[]
  reply_tree: ReplyTreeNode | null
  reply_count: number
  max_depth: number
  provenance: Provenance
  integrity: Integrity
}

// ── Transcript domain (from scripts/tools/transcribe_episodes.py dataclasses) ─

export type SegmentType = 'intro' | 'outro' | 'content'

export interface WordTimestamp {
  word: string
  start: number
  end: number
  probability: number
}

/** One speech utterance (~2-10 words). Full form in transcript.json segments[]. */
export interface SegmentResult {
  id: number
  start: number
  end: number
  text: string
  speaker: string
  segment_type: SegmentType
  chapter_id: number
  confidence: number
  words: WordTimestamp[]
  topics: string[]
  films: string[]
}

/** Compact form in transcript_segments.jsonl — no word-level data */
export interface SegmentCompact {
  id: number
  start: number
  end: number
  text: string
  speaker: string
  segment_type: SegmentType
  chapter_id: number
  confidence: number
  topics: string[]
}

/** One auto-generated chapter from transcript.json chapters[] */
export interface ChapterResult {
  index: number
  title: string
  start_time: number
  end_time: number
  duration: number
  summary: string
  segment_range: [number, number]
  word_count: number
  topics: string[]
  films: string[]
  speakers: string[]
  key_phrases: string[]
  break_score: number
  break_signals: Record<string, unknown>
}

/** Speaker cluster metadata from speaker_embeddings/clusters.json */
export interface SpeakerCluster {
  duration_s: number
  segment_count: number
  embedding_path: string
}

/** Top-level structure of transcript.json */
export interface TranscriptJson {
  meta: TranscriptMeta
  statistics: TranscriptStatistics
  chapters: ChapterResult[]
  segments: SegmentResult[]
}

export interface TranscriptMeta {
  episode_title: string
  episode_guid: string
  season: number | null
  episode: number | null
  pub_date: string
  audio_file: string
  audio_duration_seconds: number
  transcribed_at: string
  pipeline_version: string
  whisper_model: string
  device: string
  compute_type: string
  language: string
  language_probability: number
  diarization_enabled: boolean
}

export interface TranscriptStatistics {
  total_segments: number
  total_words: number
  total_duration_seconds: number
  speakers_detected: number
  topics_tagged: number
  films_mentioned: number
  chapters_generated: number
}

/** run_manifest.json at episode/transcript/run_manifest.json */
export interface RunManifest {
  canonical: string
  runs: RunManifestEntry[]
}

export interface RunManifestEntry {
  run_id: string
  created_at: string
  whisper_model: string
  diarization: boolean
  speaker_embeddings: boolean
  pipeline_version: string
}

/** extraction_report.json — lightweight completion receipt */
export interface ExtractionReport {
  episode_dir: string
  episode_title: string
  success: boolean
  error: string | null
  transcribed_at: string
  pipeline_version: string
  processing_time_seconds: number
  audio_duration_seconds: number
  segment_count: number
  word_count: number
  language: string
  speakers_detected: number
  topics_tagged: number
  films_mentioned: number
  chapters_generated: number
}

/** metadata.json at episode root */
export interface EpisodeMetadata {
  guid: string
  title: string
  pub_date_iso: string
  enclosure_url: string
  enclosure_filename: string
  enclosure_length: number
  enclosure_type: string
  description_html: string
  itunes: {
    season: number | null
    episode: number | null
    duration: string
    summary: string
    image: string
  }
  provenance: {
    rss_url: string
    scraped_at: string
    script_version: string
  }
}
