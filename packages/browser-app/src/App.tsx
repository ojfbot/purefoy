import { Provider } from 'react-redux'
import { store } from './store'
import { Dashboard } from './components/Dashboard'

// Standalone wrapper — wraps Dashboard in a store Provider for local dev.
// In the Frame shell, Dashboard's own inner Provider is used (double-Provider pattern).
export function App() {
  return (
    <Provider store={store}>
      {/* shellMode=false: show internal app header, standalone viewport heights */}
      <Dashboard shellMode={false} />
    </Provider>
  )
}
