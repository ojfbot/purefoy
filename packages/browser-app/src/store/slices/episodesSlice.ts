import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import type { PayloadAction } from '@reduxjs/toolkit'
import type { EpisodeListItem, EpisodeDetail, ChapterResult, EpisodeListParams } from '../../types'
import { episodesApi } from '../../api/client'

// ── Types ─────────────────────────────────────────────────────────────────────

export interface EpisodesFilters {
  topic: string | null
  film: string | null
  season: number | null
  page: number
  limit: number
}

interface EpisodesState {
  items: EpisodeListItem[]
  total: number
  hasMore: boolean
  filters: EpisodesFilters
  selectedSlug: string | null
  detail: EpisodeDetail | null
  chapters: ChapterResult[]
  status: 'idle' | 'loading' | 'error'
  error: string | null
}

// ── Thunks ────────────────────────────────────────────────────────────────────

export const fetchEpisodes = createAsyncThunk(
  'episodes/fetchList',
  async (params: EpisodeListParams) => {
    return episodesApi.list(params)
  }
)

export const fetchEpisodeDetail = createAsyncThunk(
  'episodes/fetchDetail',
  async (slug: string) => {
    return episodesApi.detail(slug)
  }
)

export const fetchChapters = createAsyncThunk(
  'episodes/fetchChapters',
  async (slug: string) => {
    return episodesApi.chapters(slug)
  }
)

// ── Slice ─────────────────────────────────────────────────────────────────────

const initialState: EpisodesState = {
  items: [],
  total: 0,
  hasMore: false,
  filters: { topic: null, film: null, season: null, page: 1, limit: 20 },
  selectedSlug: null,
  detail: null,
  chapters: [],
  status: 'idle',
  error: null,
}

export const episodesSlice = createSlice({
  name: 'episodes',
  initialState,
  reducers: {
    setSelectedSlug(state, action: PayloadAction<string | null>) {
      state.selectedSlug = action.payload
      if (!action.payload) {
        state.detail = null
        state.chapters = []
      }
    },
    setFilters(state, action: PayloadAction<Partial<EpisodesFilters>>) {
      state.filters = { ...state.filters, ...action.payload, page: 1 }
    },
    clearFilters(state) {
      state.filters = initialState.filters
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchEpisodes.pending, (state) => { state.status = 'loading'; state.error = null })
      .addCase(fetchEpisodes.fulfilled, (state, action) => {
        state.status = 'idle'
        // page > 1 = "load more" — append; page 1 = fresh load — replace
        if (action.meta.arg.page && action.meta.arg.page > 1) {
          state.items = [...state.items, ...action.payload.items]
        } else {
          state.items = action.payload.items
        }
        state.total = action.payload.total
        state.hasMore = action.payload.hasMore
        if (action.meta.arg.page) state.filters.page = action.meta.arg.page
      })
      .addCase(fetchEpisodes.rejected, (state, action) => {
        state.status = 'error'
        state.error = action.error.message ?? 'Unknown error'
      })
      .addCase(fetchEpisodeDetail.fulfilled, (state, action) => {
        state.detail = action.payload
      })
      .addCase(fetchChapters.fulfilled, (state, action) => {
        state.chapters = action.payload
      })
  },
})

export const { setSelectedSlug, setFilters, clearFilters } = episodesSlice.actions
export default episodesSlice.reducer
