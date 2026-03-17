import { useEffect, useState } from 'react'
import { Tabs, TabList, Tab, TabPanels, TabPanel, Heading, Tooltip } from '@carbon/react'
import { Chat, Close } from '@carbon/icons-react'
import { useAppDispatch, useAppSelector } from '../store/hooks'
import { fetchEpisodes } from '../store/slices/episodesSlice'
import { fetchForumTopics } from '../store/slices/forumSlice'
import { toggleSidebar } from '../store/slices/uiSlice'
import { EpisodeBrowser } from './EpisodeBrowser'
import { ForumBrowser } from './ForumBrowser'
import { ForumSearch } from './ForumSearch'
import { ThreadSidebar } from './ThreadSidebar'
import { CondensedChat } from './CondensedChat'
import './DashboardContent.css'

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

  const wrapperClass = [
    'dashboard-wrapper',
    sidebarExpanded ? 'with-sidebar' : '',
    shellMode ? 'shell-mode' : '',
    shellMode && chatDisplayState === 'expanded' ? 'chat-expanded' : '',
  ].filter(Boolean).join(' ')

  return (
    <>
      {/* Thread sidebar — position:fixed, sibling to dashboard-wrapper */}
      <ThreadSidebar
        isExpanded={sidebarExpanded}
        onToggle={() => dispatch(toggleSidebar())}
      />

      {/* Main content */}
      <div className={wrapperClass} data-element="app-container">
        <div className="dashboard-header">
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
        </div>

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
      </div>

      {/* Condensed chat — position:fixed, sibling to dashboard-wrapper */}
      <CondensedChat />
    </>
  )
}
