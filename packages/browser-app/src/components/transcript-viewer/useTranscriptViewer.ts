import { useEffect, useRef, useCallback } from 'react'
import { useAppDispatch, useAppSelector } from '../../store/hooks'
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
} from '../../store/slices/transcriptSlice'
import { loadTranscript, loadGoalIfExists, saveGoalData, flushReview } from '../../store/slices/transcriptSlice'
import { computeEditStats } from './utils'
import type { EditStats } from './utils'

export function useTranscriptViewer(slug: string, visible: boolean, seekToTime?: number) {
  const dispatch = useAppDispatch()
  const state = useAppSelector(s => s.transcript)
  const {
    originalSegments,
    editSegments,
    isEditing,
    reviewedSegs,
    totalSegments,
    reviewCoverage,
  } = state

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

  // Edit stats
  const editStats: EditStats = isEditing
    ? computeEditStats(editSegments, originalSegments)
    : { speakerChanges: 0, textChanges: 0, splitChanges: 0 }

  const reviewedSet = new Set(reviewedSegs)
  const origIdSet = new Set(originalSegments.map(s => s.id))
  const reviewPct = totalSegments > 0 ? Math.round(reviewCoverage * 100) : 0

  const handlers = {
    enterEdit: () => dispatch(enterEditMode()),
    exitEdit: () => dispatch(exitEditMode()),
    save: () => dispatch(saveGoalData({ slug, segments: editSegments })),
    discard: () => dispatch(discardEdits()),
    toggleSource: () => dispatch(toggleSource()),
    speakerChange: (id: number, speaker: string) => dispatch(updateSpeaker({ id, speaker })),
    textChange: (id: number, text: string) => dispatch(updateText({ id, text })),
    split: (id: number, splitPositions: number[], speakerAssignments: string[]) =>
      dispatch(splitSegment({ id, splitPositions, speakerAssignments })),
  }

  return {
    ...state,
    editStats,
    reviewedSet,
    origIdSet,
    reviewPct,
    seekRef,
    editorRef,
    handlers,
  }
}
