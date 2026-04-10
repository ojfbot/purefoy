import type { MutableRefObject } from 'react'
import type { ConversationTurn } from './utils'
import { speakerHex, formatTime } from './utils'

interface ConversationViewProps {
  turns: ConversationTurn[]
  speakerOrder: string[]
  seekToTime?: number
  seekRef: MutableRefObject<HTMLDivElement | null>
  onEnterEdit: () => void
}

export function ConversationView({ turns, speakerOrder, seekToTime, seekRef, onEnterEdit }: ConversationViewProps) {
  return (
    <div className="pt-convo">
      {turns.map((turn, ti) => {
        const color = speakerHex(turn.speaker, speakerOrder)
        const turnText = turn.segments.map(s => s.text).join(' ')
        const isSeekTarget = seekToTime != null && turn.start >= seekToTime
        return (
          <div
            key={ti}
            ref={isSeekTarget && seekRef.current === null ? seekRef : undefined}
            className="pt-turn"
            style={{ borderLeftColor: color }}
            onClick={onEnterEdit}
          >
            <div className="pt-turn__meta">
              <span className="pt-turn__speaker" style={{ color }}>
                {turn.speaker}
              </span>
              <span className="pt-turn__time">{formatTime(turn.start)}</span>
            </div>
            <p className="pt-turn__text">{turnText}</p>
          </div>
        )
      })}
    </div>
  )
}
