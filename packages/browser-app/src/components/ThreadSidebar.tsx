import { useState, useEffect } from 'react'
import { Button, Modal } from '@carbon/react'
import { Add, Chat, TrashCan } from '@carbon/icons-react'
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
import './ThreadSidebar.css'

interface ThreadSidebarProps {
  isExpanded: boolean
  onToggle: () => void
}

export function ThreadSidebar({ isExpanded, onToggle }: ThreadSidebarProps) {
  const dispatch = useAppDispatch()
  const currentThreadId = useAppSelector(s => s.chat.currentThreadId)
  const messages = useAppSelector(s => s.chat.messages)

  const [threads, setThreads] = useState<ThreadRecord[]>([])
  const [hoveredId, setHoveredId] = useState<string | null>(null)
  const [deleteModalOpen, setDeleteModalOpen] = useState(false)
  const [threadToDelete, setThreadToDelete] = useState<string | null>(null)

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

  const handleSelect = (thread: ThreadRecord) => {
    if (thread.threadId === currentThreadId) return
    dispatch(setCurrentThreadId(thread.threadId))
    dispatch(loadMessages(thread.messages))
  }

  const handleDeleteClick = (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    setThreadToDelete(id)
    setDeleteModalOpen(true)
  }

  const handleConfirmDelete = () => {
    if (!threadToDelete) return
    deleteThread(threadToDelete)
    setThreads(loadThreads())
    if (currentThreadId === threadToDelete) {
      dispatch(setCurrentThreadId(null))
      dispatch(clearMessages())
    }
    setDeleteModalOpen(false)
    setThreadToDelete(null)
  }

  return (
    <>
      <div
        className={`thread-sidebar ${isExpanded ? 'expanded' : 'collapsed'}`}
        {...(!isExpanded ? { inert: '' } : {})}
      >
        <div className="thread-sidebar-header">
          <h3 className="thread-sidebar-title">Conversations</h3>
          <div className="thread-sidebar-actions">
            <Button
              kind="primary"
              size="sm"
              hasIconOnly
              iconDescription="New conversation"
              onClick={handleNew}
            >
              <Add />
            </Button>
          </div>
        </div>

        <div className="thread-sidebar-content">
          {threads.length === 0 ? (
            <div className="thread-sidebar-empty">
              <Chat size={48} className="empty-icon" />
              <p className="empty-message">No conversations yet</p>
              <Button kind="tertiary" size="sm" onClick={handleNew}>
                Start your first conversation
              </Button>
            </div>
          ) : (
            <div className="thread-list">
              {threads.map(thread => (
                <div
                  key={thread.threadId}
                  className={`thread-item ${thread.threadId === currentThreadId ? 'active' : ''}`}
                  onClick={() => handleSelect(thread)}
                  onMouseEnter={() => setHoveredId(thread.threadId)}
                  onMouseLeave={() => setHoveredId(null)}
                >
                  <div className="thread-item-content">
                    <div className="thread-item-title">{thread.title}</div>
                    <div className="thread-item-date">{formatRelativeDate(thread.updatedAt)}</div>
                  </div>
                  {hoveredId === thread.threadId && (
                    <Button
                      kind="ghost"
                      size="sm"
                      hasIconOnly
                      iconDescription="Delete conversation"
                      className="thread-item-delete"
                      onClick={(e: React.MouseEvent) => handleDeleteClick(thread.threadId, e)}
                    >
                      <TrashCan />
                    </Button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {isExpanded && (
        <div className="thread-sidebar-overlay" onClick={onToggle} />
      )}

      <Modal
        open={deleteModalOpen}
        onRequestClose={() => setDeleteModalOpen(false)}
        onRequestSubmit={handleConfirmDelete}
        modalHeading="Delete conversation"
        modalLabel="Confirm"
        primaryButtonText="Delete"
        secondaryButtonText="Cancel"
        danger
        size="sm"
      >
        <p>Are you sure you want to delete this conversation? This cannot be undone.</p>
      </Modal>
    </>
  )
}
