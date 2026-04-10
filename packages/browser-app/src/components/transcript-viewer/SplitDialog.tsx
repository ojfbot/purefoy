import { useState } from 'react'
import type { SegmentCompact } from '../../types'

interface SplitDialogProps {
  segment: SegmentCompact
  splitPositions: number[]
  speakers: string[]
  onConfirm: (speakerAssignments: string[]) => void
  onCancel: () => void
}

export function SplitDialog({ segment, splitPositions, speakers, onConfirm, onCancel }: SplitDialogProps) {
  const words = segment.text.split(' ')
  const boundaries = [0, ...splitPositions.map(p => p + 1), words.length]
  const pieces = Array.from({ length: boundaries.length - 1 }, (_, i) =>
    words.slice(boundaries[i], boundaries[i + 1]).join(' ')
  )
  const [assignments, setAssignments] = useState<string[]>(pieces.map(() => segment.speaker))

  return (
    <div className="pt-split-dialog">
      <p className="pt-split-dialog__title">Assign speakers to {pieces.length} pieces:</p>
      {pieces.map((piece, i) => (
        <div key={i} className="pt-split-dialog__piece">
          <span className="pt-split-dialog__piece-num">{i + 1}.</span>
          <textarea
            rows={1}
            readOnly
            value={piece}
          />
          <select
            value={assignments[i]}
            onChange={e => {
              const next = [...assignments]
              next[i] = e.target.value
              setAssignments(next)
            }}
          >
            {speakers.map(sp => (
              <option key={sp} value={sp}>{sp}</option>
            ))}
          </select>
        </div>
      ))}
      <div className="pt-split-dialog__actions">
        <button className="confirm" onClick={() => onConfirm(assignments)}>
          Confirm split
        </button>
        <button onClick={onCancel}>Cancel</button>
      </div>
    </div>
  )
}
