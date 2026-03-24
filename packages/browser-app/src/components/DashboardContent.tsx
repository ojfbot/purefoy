import { useEffect, useState } from 'react'
import { Tabs, TabList, Tab, TabPanels, TabPanel, Heading, Tooltip } from '@carbon/react'
import { Chat, Close } from '@carbon/icons-react'
import { DashboardLayout } from '@ojfbot/frame-ui-components'
import '@ojfbot/frame-ui-components/styles/dashboard-layout'
import '@ojfbot/frame-ui-components/styles/thread-sidebar'
import '@ojfbot/frame-ui-components/styles/chat-shell'
import { useAppDispatch, useAppSelector } from '../store/hooks'
import { fetchEpisodes } from '../store/slices/episodesSlice'
import { fetchForumTopics } from '../store/slices/forumSlice'
import { toggleSidebar } from '../store/slices/uiSlice'
import { EpisodeBrowser } from './EpisodeBrowser'
import { ForumBrowser } from './ForumBrowser'
import { ForumSearch } from './ForumSearch'
import { ThreadSidebarConnected } from './ThreadSidebarConnected'
import { CondensedChatConnected } from './CondensedChatConnected'

interface DashboardContentProps {
  shellMode?: boolean
}

export function DashboardContent({ shellMode }: DashboardContentProps) {
  const dispatch = useAppDispatch()
  const sidebarExpanded = useAppSelector(s => s.ui.sidebarExpanded)
  const chatDisplayState = useAppSelector(s => s.chat.displayState)

  // Track which tab has been visited so we only fetch when first activated
  const [visited, setVisited] = useState<Set<number>>(new Set([0]))

  useEffect(() => {
    dispatch(fetchEpisodes({ page: 1, limit: 500 }))
  }, [dispatch])

  const handleTabChange = ({ selectedIndex }: { selectedIndex: number }) => {
    if (visited.has(selectedIndex)) return
    setVisited(prev => new Set(prev).add(selectedIndex))
    if (selectedIndex === 1) dispatch(fetchForumTopics())
  }

  return (
    <>
      {/* Thread sidebar — position:fixed, sibling to dashboard layout */}
      <ThreadSidebarConnected
        isExpanded={sidebarExpanded}
        onToggle={() => dispatch(toggleSidebar())}
      />

      {/* Main content */}
      <DashboardLayout
        shellMode={shellMode}
        sidebarExpanded={sidebarExpanded}
        chatExpanded={shellMode && chatDisplayState === 'expanded'}
      >
        <DashboardLayout.Header>
          <Heading className="page-header">Team Deakins Engine</Heading>
          <div className="dashboard-header-actions">
            <Tooltip label={sidebarExpanded ? 'Close conversations' : 'Show conversations'} align="bottom-right">
              <button
                className="sidebar-toggle-btn"
                onClick={() => dispatch(toggleSidebar())}
                aria-label="Toggle thread sidebar"
              >
                {sidebarExpanded ? <Close size={20} /> : <Chat size={20} />}
              </button>
            </Tooltip>
          </div>
        </DashboardLayout.Header>

        <Tabs onChange={handleTabChange}>
          <TabList aria-label="Purefoy navigation" contained>
            <Tab>Episodes</Tab>
            <Tab>Forum</Tab>
            <Tab>Search</Tab>
          </TabList>
          <TabPanels>
            <TabPanel><EpisodeBrowser /></TabPanel>
            <TabPanel><ForumBrowser /></TabPanel>
            <TabPanel><ForumSearch /></TabPanel>
          </TabPanels>
        </Tabs>
      </DashboardLayout>

      {/* Condensed chat — position:fixed, sibling to dashboard layout */}
      <CondensedChatConnected />
    </>
  )
}
