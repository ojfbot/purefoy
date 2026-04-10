import type { MutableRefObject } from 'react'
import type { SegmentCompact } from '../../types'
import { SegmentRow } from './SegmentRow'

interface EditGridProps {
  editSegments: SegmentCompact[]
  origIdSet: Set<number>
  originalSegments: SegmentCompact[]
  reviewedSet: Set<number>
  speakerOrder: string[]
  editorRef: MutableRefObject<HTMLDivElement | null>
  onSpeakerChange: (id: number, speaker: string) => void
  onTextChange: (id: number, text: string) => void
  onSplit: (id: number, splitPositions: number[], speakerAssignments: string[]) => void
}

export function EditGrid({
  editSegments, origIdSet, originalSegments, reviewedSet,
  speakerOrder, editorRef, onSpeakerChange, onTextChange, onSplit,
}: EditGridProps) {
  return (
    <div className="pt-editor" ref={editorRef}>
      {editSegments.map(seg => {
        const isModified = !origIdSet.has(seg.id) ||
          (() => {
            const orig = originalSegments.find(o => o.id === seg.id)
            return !!orig && (orig.speaker !== seg.speaker || orig.text !== seg.text)
          })()
        const isReviewed = reviewedSet.has(seg.id)
        return (
          <SegmentRow
            key={seg.id}
            seg={seg}
            isModified={isModified}
            isReviewed={isReviewed}
            speakers={speakerOrder}
            onSpeakerChange={onSpeakerChange}
            onTextChange={onTextChange}
            onSplit={onSplit}
          />
        )
      })}
    </div>
  )
}
