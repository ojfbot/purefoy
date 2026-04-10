import { useState } from 'react'
import type { SegmentCompact } from '../../types'
import { formatTime } from './utils'
import { SplitDialog } from './SplitDialog'

interface SegmentRowProps {
  seg: SegmentCompact
  isModified: boolean
  isReviewed: boolean
  speakers: string[]
  rowRef?: (el: HTMLDivElement | null) => void
  onSpeakerChange: (id: number, speaker: string) => void
  onTextChange: (id: number, text: string) => void
  onSplit: (id: number, splitPositions: number[], speakerAssignments: string[]) => void
}

export function SegmentRow({
  seg, isModified, isReviewed, speakers, rowRef,
  onSpeakerChange, onTextChange, onSplit,
}: SegmentRowProps) {
  const [textMode, setTextMode] = useState<'words' | 'textarea'>('words')
  const [markedSplits, setMarkedSplits] = useState<Set<number>>(new Set())
  const [showSplitDialog, setShowSplitDialog] = useState(false)

  const words = seg.text.split(' ')

  const handleWordSplitClick = (wordIdx: number) => {
    setMarkedSplits(prev => {
      const next = new Set(prev)
      if (next.has(wordIdx)) next.delete(wordIdx)
      else next.add(wordIdx)
      return next
    })
  }

  const handleSplitConfirm = (assignments: string[]) => {
    const sorted = Array.from(markedSplits).sort((a, b) => a - b)
    onSplit(seg.id, sorted, assignments)
    setMarkedSplits(new Set())
    setShowSplitDialog(false)
  }

  const handleNewSpeaker = (currentValue: string) => {
    const name = window.prompt('Enter new speaker name:', currentValue)
    if (name && name.trim()) {
      onSpeakerChange(seg.id, name.trim())
    }
  }

  const allSpeakers = speakers.includes(seg.speaker)
    ? speakers
    : [seg.speaker, ...speakers]

  return (
    <>
      <div
        ref={rowRef}
        data-seg-id={seg.id}
        className={[
          'pt-seg',
          isModified ? 'pt-seg--modified' : '',
          isReviewed ? 'pt-seg--reviewed' : '',
        ].filter(Boolean).join(' ')}
      >
        <div className="pt-seg__time">{formatTime(seg.start)}</div>

        <div className="pt-seg__speaker">
          <select
            value={seg.speaker}
            onChange={e => {
              if (e.target.value === '__new__') {
                handleNewSpeaker(seg.speaker)
              } else {
                onSpeakerChange(seg.id, e.target.value)
              }
            }}
          >
            {allSpeakers.map(sp => (
              <option key={sp} value={sp}>{sp}</option>
            ))}
            <option value="__new__">+ New speaker…</option>
          </select>
        </div>

        <div className="pt-seg__text">
          {textMode === 'textarea' ? (
            <textarea
              value={seg.text}
              onChange={e => onTextChange(seg.id, e.target.value)}
              rows={Math.max(1, Math.ceil(seg.text.length / 80))}
            />
          ) : (
            <div className="pt-seg__text-words">
              {words.map((word, wi) => (
                <span key={wi}>
                  <span className="pt-word">{word}</span>
                  {wi < words.length - 1 && (
                    <span
                      className={`pt-split-btn${markedSplits.has(wi) ? ' marked' : ''}`}
                      onClick={() => handleWordSplitClick(wi)}
                      title="Split here"
                    >
                      |
                    </span>
                  )}
                </span>
              ))}
              {markedSplits.size > 0 && (
                <span
                  className="pt-split-confirm"
                  onClick={() => setShowSplitDialog(true)}
                >
                  Split ({markedSplits.size + 1})
                </span>
              )}
            </div>
          )}
          <span
            className="pt-pencil"
            title="Edit text"
            onClick={() => setTextMode(m => m === 'words' ? 'textarea' : 'words')}
          >
            ✎
          </span>
        </div>
      </div>

      {showSplitDialog && (
        <div className="pt-split-dialog" style={{ gridColumn: '1 / -1', margin: '0 6px 4px' }}>
          <SplitDialog
            segment={seg}
            splitPositions={Array.from(markedSplits).sort((a, b) => a - b)}
            speakers={allSpeakers}
            onConfirm={handleSplitConfirm}
            onCancel={() => { setShowSplitDialog(false); setMarkedSplits(new Set()) }}
          />
        </div>
      )}
    </>
  )
}
