import type { ChatMessage } from '../store/slices/chatSlice'

const STORAGE_KEY = 'purefoy:threads'

export interface ThreadRecord {
  threadId: string
  title: string
  createdAt: string
  updatedAt: string
  messages: ChatMessage[]
}

export function loadThreads(): ThreadRecord[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as ThreadRecord[]) : []
  } catch {
    return []
  }
}

export function saveThread(thread: ThreadRecord): void {
  const threads = loadThreads().filter(t => t.threadId !== thread.threadId)
  threads.unshift(thread)
  // Keep at most 50 threads
  localStorage.setItem(STORAGE_KEY, JSON.stringify(threads.slice(0, 50)))
}

export function deleteThread(threadId: string): void {
  const threads = loadThreads().filter(t => t.threadId !== threadId)
  localStorage.setItem(STORAGE_KEY, JSON.stringify(threads))
}

export function generateThreadId(): string {
  return `thread_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}

export function deriveTitle(firstUserMessage: string): string {
  return firstUserMessage.slice(0, 60).trim() + (firstUserMessage.length > 60 ? '…' : '')
}

export function formatRelativeDate(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}
