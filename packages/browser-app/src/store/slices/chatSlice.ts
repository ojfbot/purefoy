import { createSlice } from '@reduxjs/toolkit'
import type { PayloadAction } from '@reduxjs/toolkit'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
}

export type ChatDisplayState = 'collapsed' | 'expanded' | 'minimized'

interface ChatState {
  messages: ChatMessage[]
  draftInput: string
  isLoading: boolean
  streamingContent: string
  displayState: ChatDisplayState
  unreadCount: number
  currentThreadId: string | null
}

const initialState: ChatState = {
  messages: [],
  draftInput: '',
  isLoading: false,
  streamingContent: '',
  displayState: 'collapsed',
  unreadCount: 0,
  currentThreadId: null,
}

export const chatSlice = createSlice({
  name: 'chat',
  initialState,
  reducers: {
    addMessage(state, action: PayloadAction<ChatMessage>) {
      state.messages.push(action.payload)
    },
    setDraftInput(state, action: PayloadAction<string>) {
      state.draftInput = action.payload
    },
    setIsLoading(state, action: PayloadAction<boolean>) {
      state.isLoading = action.payload
    },
    setStreamingContent(state, action: PayloadAction<string>) {
      state.streamingContent = action.payload
    },
    setDisplayState(state, action: PayloadAction<ChatDisplayState>) {
      state.displayState = action.payload
      if (action.payload === 'expanded') {
        state.unreadCount = 0
      }
    },
    incrementUnread(state) {
      if (state.displayState !== 'expanded') {
        state.unreadCount += 1
      }
    },
    clearUnread(state) {
      state.unreadCount = 0
    },
    setCurrentThreadId(state, action: PayloadAction<string | null>) {
      state.currentThreadId = action.payload
    },
    loadMessages(state, action: PayloadAction<ChatMessage[]>) {
      state.messages = action.payload
    },
    clearMessages(state) {
      state.messages = []
      state.streamingContent = ''
    },
  },
})

export const {
  addMessage,
  setDraftInput,
  setIsLoading,
  setStreamingContent,
  setDisplayState,
  incrementUnread,
  clearUnread,
  setCurrentThreadId,
  loadMessages,
  clearMessages,
} = chatSlice.actions

export default chatSlice.reducer
