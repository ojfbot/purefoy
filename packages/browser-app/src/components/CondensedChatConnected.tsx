import { ChatShell, ChatMessage, MarkdownMessage, BadgeButton, getChatMessage } from '@ojfbot/frame-ui-components'
import '@ojfbot/frame-ui-components/styles/markdown-message'
import '@ojfbot/frame-ui-components/styles/badge-button'
import type { ChatDisplayState, BadgeAction } from '@ojfbot/frame-ui-components'
import { useAppDispatch, useAppSelector } from '../store/hooks'
import {
  addMessage,
  setDraftInput,
  setIsLoading,
  setStreamingContent,
  setDisplayState,
  incrementUnread,
  setCurrentThreadId,
} from '../store/slices/chatSlice'
import { generateThreadId } from '../utils/threadStorage'

const FRAME_AGENT_URL = import.meta.env.VITE_FRAME_AGENT_URL ?? 'http://localhost:4001'

export function CondensedChatConnected() {
  const dispatch = useAppDispatch()
  const messages = useAppSelector(s => s.chat.messages)
  const draftInput = useAppSelector(s => s.chat.draftInput)
  const isLoading = useAppSelector(s => s.chat.isLoading)
  const streamingContent = useAppSelector(s => s.chat.streamingContent)
  const displayState = useAppSelector(s => s.chat.displayState)
  const unreadCount = useAppSelector(s => s.chat.unreadCount)
  const sidebarExpanded = useAppSelector(s => s.ui.sidebarExpanded)
  const currentThreadId = useAppSelector(s => s.chat.currentThreadId)

  const handleDisplayStateChange = (state: ChatDisplayState) => {
    dispatch(setDisplayState(state))
  }

  const handleSend = async (text: string) => {
    if (isLoading) return

    // Ensure thread exists
    const threadId = currentThreadId ?? generateThreadId()
    if (!currentThreadId) dispatch(setCurrentThreadId(threadId))

    const userMsg = { role: 'user' as const, content: text, timestamp: new Date().toISOString() }
    dispatch(addMessage(userMsg))
    dispatch(setDraftInput(''))
    dispatch(setIsLoading(true))
    dispatch(setStreamingContent(''))

    const history = messages.map(m => ({ role: m.role, content: m.content }))

    try {
      const res = await fetch(`${FRAME_AGENT_URL}/api/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          context: { activeAppType: 'purefoy' },
          conversationHistory: history,
        }),
      })

      if (!res.ok || !res.body) throw new Error(`Agent returned ${res.status}`)

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let accumulated = ''
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const payload = JSON.parse(line.slice(6)) as { chunk?: string; type?: string }
            if (payload.chunk) {
              accumulated += payload.chunk
              dispatch(setStreamingContent(accumulated))
            }
          } catch { /* skip malformed */ }
        }
      }

      dispatch(setStreamingContent(''))
      dispatch(addMessage({
        role: 'assistant',
        content: accumulated || '(no response)',
        timestamp: new Date().toISOString(),
      }))
      dispatch(incrementUnread())
    } catch (err) {
      dispatch(setStreamingContent(''))
      dispatch(addMessage({
        role: 'assistant',
        content: `Error: ${err instanceof Error ? err.message : 'Failed to reach agent'}`,
        timestamp: new Date().toISOString(),
      }))
    } finally {
      dispatch(setIsLoading(false))
    }
  }

  return (
    <ChatShell
      displayState={displayState}
      onDisplayStateChange={handleDisplayStateChange}
      sidebarExpanded={sidebarExpanded}
      title="Ask about episodes & forum"
      isLoading={isLoading}
      unreadCount={unreadCount}
      draftInput={draftInput}
      onDraftChange={(value) => dispatch(setDraftInput(value))}
      onSend={handleSend}
      placeholder="Ask about episodes, cinematography, forum discussions..."
      inputDisabled={isLoading}
    >
      {messages.map((msg, idx) => (
        <ChatMessage key={idx} role={msg.role}>
          {msg.role === 'user' ? (
            <span style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{msg.content}</span>
          ) : (
            <MarkdownMessage
              content={msg.content}
              suggestions={msg.suggestions}
              onExecute={(action: BadgeAction) => {
                const message = getChatMessage(action)
                if (message) handleSend(message)
              }}
              compact
            />
          )}
        </ChatMessage>
      ))}
      {streamingContent && (
        <ChatMessage role="assistant" isStreaming>
          {streamingContent}
        </ChatMessage>
      )}
    </ChatShell>
  )
}
