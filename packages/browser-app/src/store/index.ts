import { configureStore } from '@reduxjs/toolkit'
import episodesReducer from './slices/episodesSlice'
import forumReducer from './slices/forumSlice'
import chatReducer from './slices/chatSlice'
import uiReducer from './slices/uiSlice'
import transcriptReducer from './slices/transcriptSlice'

export const store = configureStore({
  reducer: {
    episodes: episodesReducer,
    forum: forumReducer,
    chat: chatReducer,
    ui: uiReducer,
    transcript: transcriptReducer,
  },
})

export type RootState = ReturnType<typeof store.getState>
export type AppDispatch = typeof store.dispatch
