import { createSlice } from '@reduxjs/toolkit'
import type { PayloadAction } from '@reduxjs/toolkit'

interface UIState {
  sidebarExpanded: boolean
}

const initialState: UIState = {
  sidebarExpanded: false,
}

export const uiSlice = createSlice({
  name: 'ui',
  initialState,
  reducers: {
    setSidebarExpanded(state, action: PayloadAction<boolean>) {
      state.sidebarExpanded = action.payload
    },
    toggleSidebar(state) {
      state.sidebarExpanded = !state.sidebarExpanded
    },
  },
})

export const { setSidebarExpanded, toggleSidebar } = uiSlice.actions
export default uiSlice.reducer
