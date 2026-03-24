import { useState, useEffect } from 'react'
import { ThreadSidebar } from '@ojfbot/frame-ui-components'
import type { ThreadItem } from '@ojfbot/frame-ui-components'
import { useAppDispatch, useAppSelector } from '../store/hooks'
import {
  setCurrentThreadId,
  loadMessages,
  clearMessages,
} from '../store/slices/chatSlice'
import {
  loadThreads,
  saveThread,
  deleteThread,
  generateThreadId,
  formatRelativeDate,
  type ThreadRecord,
} from '../utils/threadStorage'

interface ThreadSidebarConnectedProps {
  isExpanded: boolean
  onToggle: () => void
}

export function ThreadSidebarConnected({ isExpanded, onToggle }: ThreadSidebarConnectedProps) {
  const dispatch = useAppDispatch()
  const currentThreadId = useAppSelector(s => s.chat.currentThreadId)
  const messages = useAppSelector(s => s.chat.messages)

  const [threads, setThreads] = useState<ThreadRecord[]>([])

  // Load threads from localStorage on mount + when sidebar opens
  useEffect(() => {
    if (isExpanded) setThreads(loadThreads())
  }, [isExpanded])

  // Persist current thread whenever messages change
  useEffect(() => {
    if (!currentThreadId || messages.length === 0) return
    const first = messages.find(m => m.role === 'user')
    const existing = threads.find(t => t.threadId === currentThreadId)
    const record: ThreadRecord = {
      threadId: currentThreadId,
      title: existing?.title ?? (first ? first.content.slice(0, 60) : 'New conversation'),
      createdAt: existing?.createdAt ?? new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      messages,
    }
    saveThread(record)
    setThreads(loadThreads())
  }, [messages, currentThreadId]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleNew = () => {
    const id = generateThreadId()
    dispatch(setCurrentThreadId(id))
    dispatch(clearMessages())
    setThreads(loadThreads())
  }

  const handleSelect = (threadId: string) => {
    if (threadId === currentThreadId) return
    const thread = threads.find(t => t.threadId === threadId)
    if (thread) {
      dispatch(setCurrentThreadId(thread.threadId))
      dispatch(loadMessages(thread.messages))
    }
  }

  const handleDelete = (threadId: string) => {
    deleteThread(threadId)
    setThreads(loadThreads())
    if (currentThreadId === threadId) {
      dispatch(setCurrentThreadId(null))
      dispatch(clearMessages())
    }
  }

  // Map ThreadRecord[] to ThreadItem[] for the shared component
  const threadItems: ThreadItem[] = threads.map(t => ({
    threadId: t.threadId,
    title: t.title,
    updatedAt: t.updatedAt,
  }))

  return (
    <ThreadSidebar
      isExpanded={isExpanded}
      onToggle={onToggle}
      threads={threadItems}
      currentThreadId={currentThreadId}
      onCreateThread={handleNew}
      onSelectThread={handleSelect}
      onDeleteThread={handleDelete}
      formatDate={formatRelativeDate}
    />
  )
}
