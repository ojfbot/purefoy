import { describe, it } from 'vitest'

describe('Dashboard', () => {
  it.todo('renders without crashing in standalone mode (shellMode=false)')
  it.todo('renders without crashing in shell mode (shellMode=true)')
  it.todo('does NOT render app title heading when shellMode=true')
  it.todo('renders app title heading when shellMode=false')
  it.todo('inner Redux Provider is present — useAppSelector returns state not undefined')
})

describe('EpisodeBrowser', () => {
  it.todo('shows DataTableSkeleton while status=loading')
  it.todo('shows InlineNotification when status=error')
  it.todo('renders rows for each episode item')
  it.todo('dispatches setSelectedSlug on row click')
})

describe('ForumSearch', () => {
  it.todo('dispatches searchForum on button click')
  it.todo('dispatches searchForum on Enter keydown')
  it.todo('shows no-results message when results empty and query set')
  it.todo('renders result snippets')
})

describe('Settings', () => {
  it.todo('renders without crashing')
  it.todo('probe button calls /health and shows success notification')
  it.todo('probe button shows error notification on network failure')
})
