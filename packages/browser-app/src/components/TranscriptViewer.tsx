import { useEffect, useRef, useState, useCallback } from 'react'
import { InlineLoading } from '@carbon/react'
import type { SegmentCompact } from '../types'
import { useAppDispatch, useAppSelector } from '../store/hooks'
import {
  setSlug,
  enterEditMode,
  exitEditMode,
  discardEdits,
  toggleSource,
  updateSpeaker,
  updateText,
  splitSegment,
  markReviewed,
} from '../store/slices/transcriptSlice'
import { loadTranscript, loadGoalIfExists, saveGoalData, flushReview } from '../store/slices/transcriptSlice'
import './TranscriptEditor.css'

// ── Speaker colours ───────────────────────────────────────────────────────────

const SPEAKER_HEX: Record<string, string> = {
  SPEAKER_00: '#e5737f',
  SPEAKER_01: '#73b8e5',
  SPEAKER_02: '#73e5a0',
  SPEAKER_03: '#e5c873',
}
const PALETTE = ['#e5737f', '#73b8e5', '#73e5a0', '#e5c873']

function speakerHex(speaker: string, order: string[]): string {
  if (SPEAKER_HEX[speaker]) return SPEAKER_HEX[speaker]
  const idx = order.indexOf(speaker)
  if (idx >= 0) return PALETTE[idx % PALETTE.length]
  return '#888'
}

// ── Utilities ─────────────────────────────────────────────────────────────────

function formatTime(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  return `${m}:${String(s).padStart(2, '0')}`
}

interface ConversationTurn {
  speaker: string
  start: number
  segments: SegmentCompact[]
}

function groupIntoTurns(segments: SegmentCompact[]): ConversationTurn[] {
  const turns: ConversationTurn[] = []
  for (const seg of segments) {
    const last = turns[turns.length - 1]
    if (last && last.speaker === seg.speaker) {
      last.segments.push(seg)
    } else {
      turns.push({ speaker: seg.speaker, start: seg.start, segments: [seg] })
    }
  }
  return turns
}

// ── Edit stats ────────────────────────────────────────────────────────────────

interface EditStats {
  speakerChanges: number
  textChanges: number
  splitChanges: number
}

function computeEditStats(editSegs: SegmentCompact[], origSegs: SegmentCompact[]): EditStats {
  const origMap = new Map(origSegs.map(s => [s.id, s]))
  let speakerChanges = 0
  let textChanges = 0
  let splitChanges = 0
  for (const seg of editSegs) {
    const orig = origMap.get(seg.id)
    if (!orig) {
      splitChanges++
    } else {
      if (orig.speaker !== seg.speaker) speakerChanges++
      if (orig.text !== seg.text) textChanges++
    }
  }
  return { speakerChanges, textChanges, splitChanges }
}

// ── Sub-components ─────────────────────────────────────────────────────────

interface SplitDialogProps {
  segment: SegmentCompact
  splitPositions: number[]
  speakers: string[]
  onConfirm: (speakerAssignments: string[]) => void
  onCancel: () => void
}

function SplitDialog({ segment, splitPositions, speakers, onConfirm, onCancel }: SplitDialogProps) {
  const words = segment.text.split(' ')
  const boundaries = [0, ...splitPositions.map(p => p + 1), words.length]
  const pieces = Array.from({ length: boundaries.length - 1 }, (_, i) =>
    words.slice(boundaries[i], boundaries[i + 1]).join(' ')
  )
  const [assignments, setAssignments] = useState<string[]>(pieces.map(() => segment.speaker))

  return (
    <div className="pt-split-dialog">
      <p className="pt-split-dialog__title">Assign speakers to {pieces.length} pieces:</p>
      {pieces.map((piece, i) => (
        <div key={i} className="pt-split-dialog__piece">
          <span className="pt-split-dialog__piece-num">{i + 1}.</span>
          <textarea
            rows={1}
            readOnly
            value={piece}
          />
          <select
            value={assignments[i]}
            onChange={e => {
              const next = [...assignments]
              next[i] = e.target.value
              setAssignments(next)
            }}
          >
            {speakers.map(sp => (
              <option key={sp} value={sp}>{sp}</option>
            ))}
          </select>
        </div>
      ))}
      <div className="pt-split-dialog__actions">
        <button className="confirm" onClick={() => onConfirm(assignments)}>
          Confirm split
        </button>
        <button onClick={onCancel}>Cancel</button>
      </div>
    </div>
  )
}

// ── SegmentRow ────────────────────────────────────────────────────────────────

interface SegmentRowProps {
  seg: SegmentCompact
  isModified: boolean
  isReviewed: boolean
  speakers: string[]
  rowRef?: (el: HTMLDivElement | null) => void
  onSpeakerChange: (id: number, speaker: string) => void
  onTextChange: (id: number, text: string) => void
  onSplit: (id: number, splitPositions: number[], speakerAssignments: string[]) => void
}

function SegmentRow({
  seg, isModified, isReviewed, speakers, rowRef,
  onSpeakerChange, onTextChange, onSplit,
}: SegmentRowProps) {
  const [textMode, setTextMode] = useState<'words' | 'textarea'>('words')
  const [markedSplits, setMarkedSplits] = useState<Set<number>>(new Set())
  const [showSplitDialog, setShowSplitDialog] = useState(false)

  const words = seg.text.split(' ')

  const handleWordSplitClick = (wordIdx: number) => {
    setMarkedSplits(prev => {
      const next = new Set(prev)
      if (next.has(wordIdx)) next.delete(wordIdx)
      else next.add(wordIdx)
      return next
    })
  }

  const handleSplitConfirm = (assignments: string[]) => {
    const sorted = Array.from(markedSplits).sort((a, b) => a - b)
    onSplit(seg.id, sorted, assignments)
    setMarkedSplits(new Set())
    setShowSplitDialog(false)
  }

  const handleNewSpeaker = (currentValue: string) => {
    const name = window.prompt('Enter new speaker name:', currentValue)
    if (name && name.trim()) {
      onSpeakerChange(seg.id, name.trim())
    }
  }

  const allSpeakers = speakers.includes(seg.speaker)
    ? speakers
    : [seg.speaker, ...speakers]

  return (
    <>
      <div
        ref={rowRef}
        data-seg-id={seg.id}
        className={[
          'pt-seg',
          isModified ? 'pt-seg--modified' : '',
          isReviewed ? 'pt-seg--reviewed' : '',
        ].filter(Boolean).join(' ')}
      >
        {/* Time cell */}
        <div className="pt-seg__time">{formatTime(seg.start)}</div>

        {/* Speaker cell */}
        <div className="pt-seg__speaker">
          <select
            value={seg.speaker}
            onChange={e => {
              if (e.target.value === '__new__') {
                handleNewSpeaker(seg.speaker)
              } else {
                onSpeakerChange(seg.id, e.target.value)
              }
            }}
          >
            {allSpeakers.map(sp => (
              <option key={sp} value={sp}>{sp}</option>
            ))}
            <option value="__new__">+ New speaker…</option>
          </select>
        </div>

        {/* Text cell */}
        <div className="pt-seg__text">
          {textMode === 'textarea' ? (
            <textarea
              value={seg.text}
              onChange={e => onTextChange(seg.id, e.target.value)}
              rows={Math.max(1, Math.ceil(seg.text.length / 80))}
            />
          ) : (
            <div className="pt-seg__text-words">
              {words.map((word, wi) => (
                <span key={wi}>
                  <span className="pt-word">{word}</span>
                  {wi < words.length - 1 && (
                    <span
                      className={`pt-split-btn${markedSplits.has(wi) ? ' marked' : ''}`}
                      onClick={() => handleWordSplitClick(wi)}
                      title="Split here"
                    >
                      |
                    </span>
                  )}
                </span>
              ))}
              {markedSplits.size > 0 && (
                <span
                  className="pt-split-confirm"
                  onClick={() => setShowSplitDialog(true)}
                >
                  Split ({markedSplits.size + 1})
                </span>
              )}
            </div>
          )}
          <span
            className="pt-pencil"
            title="Edit text"
            onClick={() => setTextMode(m => m === 'words' ? 'textarea' : 'words')}
          >
            ✎
          </span>
        </div>
      </div>

      {showSplitDialog && (
        <div className="pt-split-dialog" style={{ gridColumn: '1 / -1', margin: '0 6px 4px' }}>
          <SplitDialog
            segment={seg}
            splitPositions={Array.from(markedSplits).sort((a, b) => a - b)}
            speakers={allSpeakers}
            onConfirm={handleSplitConfirm}
            onCancel={() => { setShowSplitDialog(false); setMarkedSplits(new Set()) }}
          />
        </div>
      )}
    </>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

interface TranscriptViewerProps {
  slug: string
  visible: boolean
  seekToTime?: number
}

export function TranscriptViewer({ slug, visible, seekToTime }: TranscriptViewerProps) {
  const dispatch = useAppDispatch()
  const {
    originalSegments,
    goalSegments,
    editSegments,
    viewingGoal,
    isEditing,
    isDirty,
    speakerOrder,
    reviewedSegs,
    totalSegments,
    reviewCoverage,
    hasGoal,
    loadStatus,
    saveStatus,
    error,
  } = useAppSelector(s => s.transcript)

  // Track previous slug + visible to know when to load
  const prevSlug = useRef<string | null>(null)
  const prevVisible = useRef(false)

  useEffect(() => {
    if (!visible) return
    const slugChanged = prevSlug.current !== slug
    const becameVisible = visible && !prevVisible.current
    prevSlug.current = slug
    prevVisible.current = visible

    if (slugChanged || becameVisible) {
      dispatch(setSlug(slug))
      dispatch(loadTranscript(slug))
      dispatch(loadGoalIfExists(slug))
    }
  }, [slug, visible, dispatch])

  useEffect(() => {
    prevVisible.current = visible
  })

  // Scroll to seekToTime when it changes
  const seekRef = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    if (seekToTime == null || !seekRef.current) return
    seekRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [seekToTime])

  // IntersectionObserver for review tracking (edit mode only)
  const pendingReviewedRef = useRef<Set<number>>(new Set())
  const reviewTimers = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map())
  const reviewFlushTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const editorRef = useRef<HTMLDivElement | null>(null)

  const scheduleReviewFlush = useCallback(() => {
    if (reviewFlushTimer.current) clearTimeout(reviewFlushTimer.current)
    reviewFlushTimer.current = setTimeout(() => {
      const pending = Array.from(pendingReviewedRef.current)
      if (pending.length > 0) {
        dispatch(markReviewed(pending))
        dispatch(flushReview({ slug, reviewedSegs: pending, totalSegments }))
        pendingReviewedRef.current = new Set()
      }
    }, 5000)
  }, [dispatch, slug, totalSegments])

  useEffect(() => {
    if (!isEditing || !editorRef.current) return

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const el = entry.target as HTMLDivElement
          const segId = parseInt(el.dataset.segId ?? '', 10)
          if (isNaN(segId)) continue

          if (entry.isIntersecting && entry.intersectionRatio >= 0.6) {
            if (!reviewTimers.current.has(segId)) {
              const timer = setTimeout(() => {
                pendingReviewedRef.current.add(segId)
                reviewTimers.current.delete(segId)
                scheduleReviewFlush()
              }, 400)
              reviewTimers.current.set(segId, timer)
            }
          } else {
            const timer = reviewTimers.current.get(segId)
            if (timer) {
              clearTimeout(timer)
              reviewTimers.current.delete(segId)
            }
          }
        }
      },
      { threshold: 0.6 }
    )

    const segRows = editorRef.current.querySelectorAll('[data-seg-id]')
    segRows.forEach(el => observer.observe(el))

    return () => {
      observer.disconnect()
      reviewTimers.current.forEach(t => clearTimeout(t))
      reviewTimers.current.clear()
      if (reviewFlushTimer.current) clearTimeout(reviewFlushTimer.current)
    }
  }, [isEditing, editSegments, scheduleReviewFlush])

  if (!visible) return null

  const isStreaming = loadStatus === 'streaming'
  const isLoaded = loadStatus === 'loaded'
  const hasError = loadStatus === 'error'

  if (isStreaming && originalSegments.length === 0) {
    return <InlineLoading description="Loading transcript…" />
  }
  if (hasError) {
    return <p className="pt-error">Error loading transcript: {error}</p>
  }

  // Source segments for read mode
  const sourceSegments = viewingGoal ? goalSegments : originalSegments

  // Filter to content segments in read mode unless small episode
  const displayReadSegs = sourceSegments.length > 50
    ? sourceSegments.filter(s => s.segment_type === 'content')
    : sourceSegments

  const turns = groupIntoTurns(displayReadSegs)

  // Edit stats
  const editStats = isEditing
    ? computeEditStats(editSegments, originalSegments)
    : { speakerChanges: 0, textChanges: 0, splitChanges: 0 }

  const reviewedSet = new Set(reviewedSegs)
  const origIdSet = new Set(originalSegments.map(s => s.id))

  const reviewPct = totalSegments > 0
    ? Math.round(reviewCoverage * 100)
    : 0

  const handleEnterEdit = () => dispatch(enterEditMode())
  const handleExitEdit = () => dispatch(exitEditMode())
  const handleSave = () => {
    dispatch(saveGoalData({ slug, segments: editSegments }))
  }
  const handleDiscard = () => dispatch(discardEdits())
  const handleToggleSource = () => dispatch(toggleSource())

  const handleSpeakerChange = (id: number, speaker: string) => {
    dispatch(updateSpeaker({ id, speaker }))
  }
  const handleTextChange = (id: number, text: string) => {
    dispatch(updateText({ id, text }))
  }
  const handleSplit = (id: number, splitPositions: number[], speakerAssignments: string[]) => {
    dispatch(splitSegment({ id, splitPositions, speakerAssignments }))
  }

  const statsParts: string[] = []
  if (editStats.speakerChanges > 0) statsParts.push(`${editStats.speakerChanges} speaker`)
  if (editStats.textChanges > 0) statsParts.push(`${editStats.textChanges} text`)
  if (editStats.splitChanges > 0) statsParts.push(`${editStats.splitChanges} split`)

  return (
    <div className="purefoy-transcript-editor">
      {/* Toolbar */}
      <div className="pt-toolbar">
        {hasGoal && (
          <div className="pt-source-toggle">
            <button
              className={!viewingGoal ? 'active' : ''}
              onClick={() => viewingGoal && handleToggleSource()}
            >
              Original
            </button>
            <button
              className={viewingGoal ? 'active' : ''}
              onClick={() => !viewingGoal && handleToggleSource()}
            >
              Goal
            </button>
          </div>
        )}

        <button
          className={isEditing ? 'active' : ''}
          onClick={isEditing ? handleExitEdit : handleEnterEdit}
          disabled={isStreaming}
        >
          {isEditing ? 'Editing' : 'Edit'}
        </button>

        {isEditing && (
          <>
            <button
              className="primary"
              onClick={handleSave}
              disabled={!isDirty || saveStatus === 'saving'}
            >
              {saveStatus === 'saving' ? 'Saving…' : 'Save as Goal Data ✓'}
            </button>

            {isDirty && (
              <button className="danger" onClick={handleDiscard}>
                Discard
              </button>
            )}

            {statsParts.length > 0 && (
              <span className="pt-toolbar__stats">
                {statsParts.join(' · ')}
              </span>
            )}

            <span className="pt-toolbar__review-pct">
              {reviewedSegs.length}/{totalSegments} reviewed ({reviewPct}%)
            </span>
          </>
        )}

        {isStreaming && (
          <span style={{ fontSize: '0.7rem', color: '#888' }}>
            Streaming… {originalSegments.length}
          </span>
        )}
      </div>

      {/* Review progress bar (edit mode) */}
      {isEditing && (
        <div className="pt-review-bar">
          <progress value={reviewCoverage} max={1} />
        </div>
      )}

      {/* Conversation view (read mode) */}
      {!isEditing && isLoaded && (
        <div className="pt-convo">
          {turns.map((turn, ti) => {
            const color = speakerHex(turn.speaker, speakerOrder)
            const turnText = turn.segments.map(s => s.text).join(' ')
            const isSeekTarget = seekToTime != null && turn.start >= seekToTime
            return (
              <div
                key={ti}
                ref={isSeekTarget && seekRef.current === null ? seekRef : undefined}
                className="pt-turn"
                style={{ borderLeftColor: color }}
                onClick={handleEnterEdit}
              >
                <div className="pt-turn__meta">
                  <span className="pt-turn__speaker" style={{ color }}>
                    {turn.speaker}
                  </span>
                  <span className="pt-turn__time">{formatTime(turn.start)}</span>
                </div>
                <p className="pt-turn__text">{turnText}</p>
              </div>
            )
          })}
        </div>
      )}

      {/* Edit grid */}
      {isEditing && (
        <div className="pt-editor" ref={editorRef}>
          {editSegments.map(seg => {
            const isModified = !origIdSet.has(seg.id) ||
              (() => {
                const orig = originalSegments.find(o => o.id === seg.id)
                return !!orig && (orig.speaker !== seg.speaker || orig.text !== seg.text)
              })()
            const isReviewed = reviewedSet.has(seg.id)
            return (
              <SegmentRow
                key={seg.id}
                seg={seg}
                isModified={isModified}
                isReviewed={isReviewed}
                speakers={speakerOrder}
                onSpeakerChange={handleSpeakerChange}
                onTextChange={handleTextChange}
                onSplit={handleSplit}
              />
            )
          })}
        </div>
      )}
    </div>
  )
}
