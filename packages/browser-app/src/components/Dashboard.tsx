import { Provider } from 'react-redux'
import { ErrorBoundary } from '@ojfbot/frame-ui-components'
import { store } from '../store'
import { DashboardContent } from './DashboardContent'

interface DashboardProps {
  /**
   * True when mounted inside the Frame shell host.
   * Suppresses the internal app title heading and activates flex-height chain
   * so tab content fills the shell frame instead of standalone viewport heights.
   * Does NOT remove navigation or controls.
   */
  shellMode?: boolean
  /** Shell-assigned instance ID — not used by purefoy (singleton), accepted to match shell contract */
  instanceId?: string
  /** Shell-assigned thread ID for AI context routing */
  threadId?: string | null
}

// SCAFFOLD: Double-Provider pattern — required for Frame OS Module Federation.
// The shell mounts this component under the shell's own Redux Provider which has
// no purefoy slices. Without the inner Provider every useAppSelector returns undefined.
// Standalone App.tsx also wraps with the same store — inner Provider wins, harmless.
//
// DO NOT remove or move this Provider. Retrofitting it later caused multi-session
// debugging across cv-builder, BlogEngine, and TripPlanner. See shell-mf-integration.md.
export function Dashboard({ shellMode }: DashboardProps) {
  return (
    <Provider store={store}>
      <ErrorBoundary>
        <DashboardContent shellMode={shellMode} />
      </ErrorBoundary>
    </Provider>
  )
}

// Default export required for Module Federation dynamic import
export default Dashboard
