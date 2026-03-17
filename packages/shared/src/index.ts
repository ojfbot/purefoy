// Single entry point for all shared types.
// Consumers: packages/api and packages/browser-app
//
// Generated types (from Python Pydantic/dataclass schemas) — do not edit manually.
// Regenerate with: pnpm codegen
export type * from './generated/schema.js'
// Hand-written HTTP API envelope types — edit directly.
export type * from './api-types.js'

// Named aliases for Python on-disk data shapes so consumers can import by name.
// openapi-typescript nests all schemas inside components['schemas'] — these
// aliases flatten that for ergonomic use throughout the codebase.
import type { components } from './generated/schema.js'
export type PostLeaf          = components['schemas']['PostLeaf']
export type TopicLeaf         = components['schemas']['TopicLeaf']
export type ForumLeaf         = components['schemas']['ForumLeaf']
export type PostIds           = components['schemas']['PostIds']
export type PostType          = components['schemas']['PostType']
export type Author            = components['schemas']['Author']
export type Timestamps        = components['schemas']['Timestamps']
export type Integrity         = components['schemas']['Integrity']
export type Provenance        = components['schemas']['Provenance']
export type HttpProvenance    = components['schemas']['HttpProvenance']
export type ContentBlock      = components['schemas']['ContentBlock']
export type Quote             = components['schemas']['Quote']
export type Link              = components['schemas']['Link']
export type Media             = components['schemas']['Media']
export type ChapterResult     = components['schemas']['ChapterResult']
export type SegmentResult     = components['schemas']['SegmentResult']
export type SegmentCompact    = components['schemas']['SegmentCompact']
export type WordTimestamp      = components['schemas']['WordTimestamp']
export type EpisodeMetadata   = components['schemas']['EpisodeMetadata']
export type ExtractionReport  = components['schemas']['ExtractionReport']
export type RunManifest       = components['schemas']['RunManifest']
export type RunManifestEntry  = components['schemas']['RunManifestEntry']
