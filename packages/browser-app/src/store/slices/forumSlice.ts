import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import type { PayloadAction } from '@reduxjs/toolkit'
import type { ForumTopicSummary, ForumPostSummary, ForumSearchResult } from '../../types'
import { forumApi } from '../../api/client'

// ── Types ─────────────────────────────────────────────────────────────────────

interface ForumState {
  topics: ForumTopicSummary[]
  topicsTotal: number
  selectedTopicSlug: string | null
  selectedTopicPosts: ForumPostSummary[]
  searchQuery: string
  searchResults: ForumSearchResult[]
  status: 'idle' | 'loading' | 'error'
  error: string | null
}

// ── Thunks ────────────────────────────────────────────────────────────────────

export const fetchForumTopics = createAsyncThunk(
  'forum/fetchTopics',
  async () => {
    return forumApi.topics()
  }
)

export const fetchTopicDetail = createAsyncThunk(
  'forum/fetchTopicDetail',
  async (slug: string) => {
    return forumApi.topicDetail(slug)
  }
)

export const searchForum = createAsyncThunk(
  'forum/search',
  async (query: string) => {
    return forumApi.search(query)
  }
)

// ── Slice ─────────────────────────────────────────────────────────────────────

const initialState: ForumState = {
  topics: [],
  topicsTotal: 0,
  selectedTopicSlug: null,
  selectedTopicPosts: [],
  searchQuery: '',
  searchResults: [],
  status: 'idle',
  error: null,
}

export const forumSlice = createSlice({
  name: 'forum',
  initialState,
  reducers: {
    setSelectedTopicSlug(state, action: PayloadAction<string | null>) {
      state.selectedTopicSlug = action.payload
      if (!action.payload) state.selectedTopicPosts = []
    },
    setSearchQuery(state, action: PayloadAction<string>) {
      state.searchQuery = action.payload
    },
    clearSearch(state) {
      state.searchQuery = ''
      state.searchResults = []
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchForumTopics.pending, (state) => { state.status = 'loading'; state.error = null })
      .addCase(fetchForumTopics.fulfilled, (state, action) => {
        state.status = 'idle'
        state.topics = action.payload.items
        state.topicsTotal = action.payload.total
      })
      .addCase(fetchForumTopics.rejected, (state, action) => {
        state.status = 'error'
        state.error = action.error.message ?? 'Unknown error'
      })
      .addCase(fetchTopicDetail.fulfilled, (state, action) => {
        state.selectedTopicPosts = action.payload.posts
      })
      .addCase(searchForum.fulfilled, (state, action) => {
        state.searchResults = action.payload
      })
  },
})

export const { setSelectedTopicSlug, setSearchQuery, clearSearch } = forumSlice.actions
export default forumSlice.reducer
