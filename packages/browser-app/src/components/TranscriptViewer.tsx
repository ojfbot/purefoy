import { useEffect, useRef, useState } from 'react'
import { InlineLoading, Tag } from '@carbon/react'
import type { SegmentCompact } from '../types'
import { episodesApi } from '../api/client'

interface TranscriptViewerProps {
  slug: string
  visible: boolean
  /** Highlight segments at or after this chapter start time (seconds) */
  seekToTime?: number
}

// Speaker colour palette — maps anonymous cluster labels to consistent colours
const SPEAKER_COLOURS: Record<string, string> = {
  SPEAKER_00: 'blue',
  SPEAKER_01: 'green',
  SPEAKER_02: 'teal',
  SPEAKER_03: 'purple',
}
const FALLBACK_COLOUR = 'gray'

function speakerColour(speaker: string): string {
  return SPEAKER_COLOURS[speaker] ?? FALLBACK_COLOUR
}

function formatTime(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  return `${m}:${String(s).padStart(2, '0')}`
}

export function TranscriptViewer({ slug, visible, seekToTime }: TranscriptViewerProps) {
  const [segments, setSegments] = useState<SegmentCompact[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [streamProgress, setStreamProgress] = useState(0)
  const abortRef = useRef<AbortController | null>(null)
  const seekRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!visible || segments.length > 0) return  // don't re-fetch if already loaded
    abortRef.current?.abort()
    abortRef.current = new AbortController()

    setLoading(true)
    setError(null)
    setStreamProgress(0)

    const collected: SegmentCompact[] = []

    episodesApi.transcriptStream(slug, abortRef.current.signal)
      .then(async res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        if (!res.body) throw new Error('No response body')

        const reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() ?? ''  // last partial line stays in buffer

          for (const line of lines) {
            const trimmed = line.trim()
            if (!trimmed) continue
            try {
              const seg = JSON.parse(trimmed) as SegmentCompact
              collected.push(seg)
              // Batch UI updates every 200 segments to avoid excessive re-renders
              if (collected.length % 200 === 0) {
                setSegments([...collected])
                setStreamProgress(collected.length)
              }
            } catch {
              // malformed line — skip
            }
          }
        }

        // Flush remaining
        if (buffer.trim()) {
          try { collected.push(JSON.parse(buffer) as SegmentCompact) } catch { /* skip */ }
        }

        setSegments([...collected])
        setLoading(false)
      })
      .catch(err => {
        if (err instanceof Error && err.name === 'AbortError') return
        setError(err instanceof Error ? err.message : 'Unknown error')
        setLoading(false)
      })

    return () => abortRef.current?.abort()
  }, [slug, visible])  // intentionally excludes segments.length from deps

  // Scroll to seekToTime when it changes
  useEffect(() => {
    if (seekToTime == null || !seekRef.current) return
    seekRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [seekToTime])

  if (!visible) return null

  if (loading && segments.length === 0) {
    return <InlineLoading description="Loading transcript…" />
  }
  if (error) {
    return <p style={{ color: 'var(--cds-danger-01)' }}>Error loading transcript: {error}</p>
  }

  // Filter to content segments only (skip intro/outro boilerplate) unless small episode
  const displaySegments = segments.length > 50
    ? segments.filter(s => s.segment_type === 'content')
    : segments

  return (
    <div className="purefoy-transcript">
      {loading && (
        <p className="purefoy-transcript__progress" style={{ color: 'var(--cds-text-secondary)', fontSize: '0.75rem' }}>
          Loading… {streamProgress} segments
        </p>
      )}

      {displaySegments.map(seg => {
        const isSeekTarget = seekToTime != null && seg.start >= seekToTime
        return (
          <div
            key={seg.id}
            ref={isSeekTarget && seekRef.current === null ? seekRef : undefined}
            className={[
              'purefoy-transcript__segment',
              `purefoy-transcript__segment--${seg.segment_type}`,
            ].join(' ')}
          >
            <div className="purefoy-transcript__segment-meta">
              {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
              <Tag size="sm" type={speakerColour(seg.speaker) as any}>
                {seg.speaker}
              </Tag>
              <span className="purefoy-transcript__time">{formatTime(seg.start)}</span>
              {(seg.topics?.length ?? 0) > 0 && (
                <span className="purefoy-transcript__topics">
                  {seg.topics!.slice(0, 2).map(t => (
                    <Tag key={t} size="sm" type="gray">{t}</Tag>
                  ))}
                </span>
              )}
            </div>
            <p className="purefoy-transcript__text">{seg.text}</p>
          </div>
        )
      })}
    </div>
  )
}
