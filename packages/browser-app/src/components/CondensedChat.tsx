import { useRef, useEffect, useCallback } from 'react'
import { TextInput, TextArea, Button, IconButton, InlineLoading, Tile } from '@carbon/react'
import { SendAlt, Minimize, ChatBot } from '@carbon/icons-react'
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
import './CondensedChat.css'

const FRAME_AGENT_URL = import.meta.env.VITE_FRAME_AGENT_URL ?? 'http://localhost:4001'

export function CondensedChat() {
  const dispatch = useAppDispatch()
  const messages = useAppSelector(s => s.chat.messages)
  const draftInput = useAppSelector(s => s.chat.draftInput)
  const isLoading = useAppSelector(s => s.chat.isLoading)
  const streamingContent = useAppSelector(s => s.chat.streamingContent)
  const displayState = useAppSelector(s => s.chat.displayState)
  const unreadCount = useAppSelector(s => s.chat.unreadCount)
  const sidebarExpanded = useAppSelector(s => s.ui.sidebarExpanded)
  const currentThreadId = useAppSelector(s => s.chat.currentThreadId)

  const isExpanded = displayState === 'expanded'
  const isMinimized = displayState === 'minimized'

  const inputRef = useRef<HTMLInputElement>(null)
  const textAreaRef = useRef<HTMLTextAreaElement>(null)
  const messagesContainerRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = useCallback(() => {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        if (messagesContainerRef.current) {
          messagesContainerRef.current.scrollTop = messagesContainerRef.current.scrollHeight
        }
      })
    })
  }, [])

  useEffect(() => {
    if (isExpanded) {
      setTimeout(() => textAreaRef.current?.focus(), 100)
    }
  }, [isExpanded])

  useEffect(() => {
    scrollToBottom()
  }, [messages, streamingContent, scrollToBottom])

  const handleSend = async () => {
    const text = draftInput.trim()
    if (!text || isLoading) return

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
            } else if (payload.type === 'done') {
              // Final message committed below
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

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  if (isMinimized) return null

  return (
    <div
      className={[
        'condensed-chat',
        isExpanded ? 'expanded' : '',
        sidebarExpanded ? 'with-sidebar' : '',
      ].filter(Boolean).join(' ')}
      data-element="chat-window"
    >
      {/* Header */}
      <div
        className="condensed-header"
        onClick={() => { if (!isExpanded) dispatch(setDisplayState('expanded')) }}
        style={{ cursor: isExpanded ? 'default' : 'pointer' }}
      >
        <div className="header-left">
          <ChatBot size={20} />
          <span className="header-title">Ask about episodes & forum</span>
          {!isExpanded && isLoading && (
            <div className="header-thinking-spinner">
              <InlineLoading status="active" />
            </div>
          )}
          {!isExpanded && !isLoading && unreadCount > 0 && (
            <span className="unread-badge">new</span>
          )}
        </div>
        <div className="header-actions">
          {isExpanded && (
            <IconButton
              label="Minimize chat"
              size="sm"
              kind="ghost"
              onClick={(e: React.MouseEvent) => {
                e.stopPropagation()
                dispatch(setDisplayState('collapsed'))
              }}
            >
              <Minimize size={16} />
            </IconButton>
          )}
        </div>
      </div>

      {/* Messages */}
      {isExpanded && (
        <div className="chat-messages-container" ref={messagesContainerRef}>
          {messages.map((msg, idx) => (
            <Tile key={idx} className={`message-tile ${msg.role}`}>
              <div className="message-header">
                <strong>{msg.role === 'user' ? 'You' : 'Purefoy AI'}</strong>
              </div>
              <div className="message-content">
                <div className={msg.role === 'user' ? 'user-message' : ''}>{msg.content}</div>
              </div>
            </Tile>
          ))}
          {streamingContent && (
            <Tile className="message-tile assistant streaming">
              <div className="message-header">
                <strong>Purefoy AI</strong>
                <span className="streaming-indicator">typing…</span>
              </div>
              <div className="message-content">{streamingContent}</div>
            </Tile>
          )}
        </div>
      )}

      {/* Input */}
      <div className="condensed-input-wrapper">
        <div className="textarea-container-condensed">
          {isExpanded ? (
            <TextArea
              ref={textAreaRef}
              className="condensed-chat-textarea"
              labelText=""
              hideLabel
              placeholder="Ask about episodes, cinematography, forum discussions…"
              rows={3}
              value={draftInput}
              onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => dispatch(setDraftInput(e.target.value))}
              onKeyDown={handleKeyDown}
              disabled={isLoading}
            />
          ) : (
            <TextInput
              ref={inputRef}
              id="condensed-chat-input"
              labelText=""
              hideLabel
              placeholder="Ask about episodes or forum…"
              value={draftInput}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => dispatch(setDraftInput(e.target.value))}
              onKeyDown={handleKeyDown}
              disabled={isLoading}
            />
          )}
        </div>
        <div className="input-actions-condensed">
          <Button
            className="send-button-inline-condensed"
            renderIcon={SendAlt}
            hasIconOnly
            iconDescription="Send"
            kind="primary"
            size="sm"
            onClick={handleSend}
            disabled={isLoading || !draftInput.trim()}
          />
        </div>
      </div>
    </div>
  )
}
