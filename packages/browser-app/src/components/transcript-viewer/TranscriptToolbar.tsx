import type { EditStats } from './utils'

interface TranscriptToolbarProps {
  hasGoal: boolean
  viewingGoal: boolean
  isEditing: boolean
  isStreaming: boolean
  isDirty: boolean
  saveStatus: string
  editStats: EditStats
  reviewedCount: number
  totalSegments: number
  reviewPct: number
  streamingCount: number
  onToggleSource: () => void
  onEnterEdit: () => void
  onExitEdit: () => void
  onSave: () => void
  onDiscard: () => void
}

export function TranscriptToolbar({
  hasGoal, viewingGoal, isEditing, isStreaming, isDirty, saveStatus,
  editStats, reviewedCount, totalSegments, reviewPct, streamingCount,
  onToggleSource, onEnterEdit, onExitEdit, onSave, onDiscard,
}: TranscriptToolbarProps) {
  const statsParts: string[] = []
  if (editStats.speakerChanges > 0) statsParts.push(`${editStats.speakerChanges} speaker`)
  if (editStats.textChanges > 0) statsParts.push(`${editStats.textChanges} text`)
  if (editStats.splitChanges > 0) statsParts.push(`${editStats.splitChanges} split`)

  return (
    <div className="pt-toolbar">
      {hasGoal && (
        <div className="pt-source-toggle">
          <button
            className={!viewingGoal ? 'active' : ''}
            onClick={() => viewingGoal && onToggleSource()}
          >
            Original
          </button>
          <button
            className={viewingGoal ? 'active' : ''}
            onClick={() => !viewingGoal && onToggleSource()}
          >
            Goal
          </button>
        </div>
      )}

      <button
        className={isEditing ? 'active' : ''}
        onClick={isEditing ? onExitEdit : onEnterEdit}
        disabled={isStreaming}
      >
        {isEditing ? 'Editing' : 'Edit'}
      </button>

      {isEditing && (
        <>
          <button
            className="primary"
            onClick={onSave}
            disabled={!isDirty || saveStatus === 'saving'}
          >
            {saveStatus === 'saving' ? 'Saving…' : 'Save as Goal Data ✓'}
          </button>

          {isDirty && (
            <button className="danger" onClick={onDiscard}>
              Discard
            </button>
          )}

          {statsParts.length > 0 && (
            <span className="pt-toolbar__stats">
              {statsParts.join(' · ')}
            </span>
          )}

          <span className="pt-toolbar__review-pct">
            {reviewedCount}/{totalSegments} reviewed ({reviewPct}%)
          </span>
        </>
      )}

      {isStreaming && (
        <span style={{ fontSize: '0.7rem', color: '#888' }}>
          Streaming… {streamingCount}
        </span>
      )}
    </div>
  )
}
