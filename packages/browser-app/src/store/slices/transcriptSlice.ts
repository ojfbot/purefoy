import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import type { PayloadAction } from '@reduxjs/toolkit'
import type { SegmentCompact, GoalManifest } from '../../types'
import { episodesApi } from '../../api/client'

// ── Types ─────────────────────────────────────────────────────────────────────

interface TranscriptState {
  slug: string | null
  // Loaded data
  originalSegments: SegmentCompact[]
  goalSegments: SegmentCompact[]
  // Working state
  editSegments: SegmentCompact[]
  viewingGoal: boolean
  isEditing: boolean
  isDirty: boolean
  // Derived speaker metadata
  speakerOrder: string[]
  // Review
  reviewedSegs: number[]
  totalSegments: number
  reviewCoverage: number
  // Goal meta
  goalMeta: GoalManifest | null
  hasGoal: boolean
  // Loading
  loadStatus: 'idle' | 'streaming' | 'loaded' | 'error'
  saveStatus: 'idle' | 'saving' | 'error'
  error: string | null
}

// ── Helpers ───────────────────────────────────────────────────────────────────

async function streamNdjson(response: Response): Promise<SegmentCompact[]> {
  if (!response.ok) throw new Error(`HTTP ${response.status}`)
  if (!response.body) throw new Error('No response body')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  const collected: SegmentCompact[] = []

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''
    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed) continue
      try {
        collected.push(JSON.parse(trimmed) as SegmentCompact)
      } catch { /* skip malformed line */ }
    }
  }
  if (buffer.trim()) {
    try { collected.push(JSON.parse(buffer) as SegmentCompact) } catch { /* skip */ }
  }
  return collected
}

function deriveSpeakerOrder(segments: SegmentCompact[]): string[] {
  const seen = new Set<string>()
  const order: string[] = []
  for (const seg of segments) {
    if (!seen.has(seg.speaker)) {
      seen.add(seg.speaker)
      order.push(seg.speaker)
    }
  }
  return order
}

function nextId(segments: SegmentCompact[]): number {
  if (segments.length === 0) return 1
  return Math.max(...segments.map(s => s.id)) + 1
}

// ── Thunks ────────────────────────────────────────────────────────────────────

export const loadTranscript = createAsyncThunk(
  'transcript/loadTranscript',
  async (slug: string) => {
    const response = await episodesApi.transcriptStream(slug)
    return streamNdjson(response)
  }
)

export const loadGoalIfExists = createAsyncThunk(
  'transcript/loadGoalIfExists',
  async (slug: string) => {
    const response = await episodesApi.transcriptGoalStream(slug)
    if (response.status === 404) return []
    return streamNdjson(response)
  }
)

export const saveGoalData = createAsyncThunk(
  'transcript/saveGoalData',
  async ({ slug, segments }: { slug: string; segments: SegmentCompact[] }) => {
    return episodesApi.saveGoal(slug, segments)
  }
)

export const flushReview = createAsyncThunk(
  'transcript/flushReview',
  async ({ slug, reviewedSegs, totalSegments }: { slug: string; reviewedSegs: number[]; totalSegments: number }) => {
    return episodesApi.updateReview(slug, reviewedSegs, totalSegments)
  }
)

// ── Initial state ─────────────────────────────────────────────────────────────

const initialState: TranscriptState = {
  slug: null,
  originalSegments: [],
  goalSegments: [],
  editSegments: [],
  viewingGoal: false,
  isEditing: false,
  isDirty: false,
  speakerOrder: [],
  reviewedSegs: [],
  totalSegments: 0,
  reviewCoverage: 0,
  goalMeta: null,
  hasGoal: false,
  loadStatus: 'idle',
  saveStatus: 'idle',
  error: null,
}

// ── Slice ─────────────────────────────────────────────────────────────────────

export const transcriptSlice = createSlice({
  name: 'transcript',
  initialState,
  reducers: {
    setSlug(state, action: PayloadAction<string | null>) {
      if (state.slug !== action.payload) {
        // Reset when slug changes
        Object.assign(state, { ...initialState, slug: action.payload })
      }
    },

    enterEditMode(state) {
      state.isEditing = true
      // Copy source segments (goal if viewing goal, otherwise original)
      state.editSegments = state.viewingGoal
        ? [...state.goalSegments]
        : [...state.originalSegments]
      state.isDirty = false
    },

    exitEditMode(state) {
      state.isEditing = false
    },

    discardEdits(state) {
      state.editSegments = state.viewingGoal
        ? [...state.goalSegments]
        : [...state.originalSegments]
      state.isDirty = false
    },

    toggleSource(state) {
      if (!state.hasGoal) return
      state.viewingGoal = !state.viewingGoal
      if (state.isEditing) {
        state.editSegments = state.viewingGoal
          ? [...state.goalSegments]
          : [...state.originalSegments]
        state.isDirty = false
      }
    },

    updateSpeaker(state, action: PayloadAction<{ id: number; speaker: string }>) {
      const seg = state.editSegments.find(s => s.id === action.payload.id)
      if (seg) {
        seg.speaker = action.payload.speaker
        state.isDirty = true
        state.speakerOrder = deriveSpeakerOrder(state.editSegments)
      }
    },

    updateText(state, action: PayloadAction<{ id: number; text: string }>) {
      const seg = state.editSegments.find(s => s.id === action.payload.id)
      if (seg) {
        seg.text = action.payload.text
        state.isDirty = true
      }
    },

    splitSegment(state, action: PayloadAction<{
      id: number
      splitPositions: number[]  // word indices (0-indexed) after which to split
      speakerAssignments: string[]  // length = splitPositions.length + 1
    }>) {
      const { id, splitPositions, speakerAssignments } = action.payload
      const idx = state.editSegments.findIndex(s => s.id === id)
      if (idx === -1) return
      const orig = state.editSegments[idx]
      const words = orig.text.split(' ')
      const totalWords = words.length

      // Build word ranges for each piece
      // splitPositions are the indices AFTER which to cut (0-indexed word index)
      const boundaries = [0, ...splitPositions.map(p => p + 1), totalWords]
      const pieces: Array<{ words: string[]; wordStart: number; wordEnd: number }> = []
      for (let i = 0; i < boundaries.length - 1; i++) {
        pieces.push({
          words: words.slice(boundaries[i], boundaries[i + 1]),
          wordStart: boundaries[i],
          wordEnd: boundaries[i + 1],
        })
      }

      const totalDuration = orig.end - orig.start
      const newSegs: SegmentCompact[] = []
      let baseId = nextId(state.editSegments)
      const totalPieces = pieces.length

      for (let i = 0; i < totalPieces; i++) {
        const piece = pieces[i]
        const startFrac = totalWords > 0 ? piece.wordStart / totalWords : i / totalPieces
        const endFrac = totalWords > 0 ? piece.wordEnd / totalWords : (i + 1) / totalPieces
        newSegs.push({
          ...orig,
          id: i === 0 ? id : baseId++,
          text: piece.words.join(' '),
          speaker: speakerAssignments[i] ?? orig.speaker,
          start: orig.start + startFrac * totalDuration,
          end: orig.start + endFrac * totalDuration,
        })
      }

      state.editSegments.splice(idx, 1, ...newSegs)
      state.isDirty = true
      state.speakerOrder = deriveSpeakerOrder(state.editSegments)
    },

    markReviewed(state, action: PayloadAction<number[]>) {
      const newSet = new Set([...state.reviewedSegs, ...action.payload])
      state.reviewedSegs = Array.from(newSet).sort((a, b) => a - b)
      const total = state.totalSegments || 1
      state.reviewCoverage = state.reviewedSegs.length / total
    },
  },
  extraReducers: (builder) => {
    // loadTranscript
    builder
      .addCase(loadTranscript.pending, (state) => {
        state.loadStatus = 'streaming'
        state.error = null
        state.originalSegments = []
        state.editSegments = []
      })
      .addCase(loadTranscript.fulfilled, (state, action) => {
        state.loadStatus = 'loaded'
        state.originalSegments = action.payload
        state.totalSegments = action.payload.length
        state.speakerOrder = deriveSpeakerOrder(action.payload)
        // If not in edit mode, editSegments stays empty (read mode uses original directly)
      })
      .addCase(loadTranscript.rejected, (state, action) => {
        state.loadStatus = 'error'
        state.error = action.error.message ?? 'Failed to load transcript'
      })

    // loadGoalIfExists
    builder
      .addCase(loadGoalIfExists.fulfilled, (state, action) => {
        state.goalSegments = action.payload
        state.hasGoal = action.payload.length > 0
      })
      .addCase(loadGoalIfExists.rejected, () => {
        // silently ignore — no goal data is fine
      })

    // saveGoalData
    builder
      .addCase(saveGoalData.pending, (state) => {
        state.saveStatus = 'saving'
      })
      .addCase(saveGoalData.fulfilled, (state, action) => {
        state.saveStatus = 'idle'
        state.goalMeta = action.payload
        state.goalSegments = [...state.editSegments]
        state.hasGoal = true
        state.isDirty = false
      })
      .addCase(saveGoalData.rejected, (state) => {
        state.saveStatus = 'error'
      })

    // flushReview
    builder
      .addCase(flushReview.fulfilled, (state, action) => {
        state.reviewCoverage = action.payload.reviewCoverage
        state.reviewedSegs = action.payload.reviewedSegments
      })
  },
})

export const {
  setSlug,
  enterEditMode,
  exitEditMode,
  discardEdits,
  toggleSource,
  updateSpeaker,
  updateText,
  splitSegment,
  markReviewed,
} = transcriptSlice.actions

export default transcriptSlice.reducer
