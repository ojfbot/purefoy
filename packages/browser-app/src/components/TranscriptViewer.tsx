import { InlineLoading } from '@carbon/react'
import { useTranscriptViewer } from './transcript-viewer/useTranscriptViewer'
import { groupIntoTurns } from './transcript-viewer/utils'
import { TranscriptToolbar } from './transcript-viewer/TranscriptToolbar'
import { ConversationView } from './transcript-viewer/ConversationView'
import { EditGrid } from './transcript-viewer/EditGrid'
import './TranscriptEditor.css'

interface TranscriptViewerProps {
  slug: string
  visible: boolean
  seekToTime?: number
}

export function TranscriptViewer({ slug, visible, seekToTime }: TranscriptViewerProps) {
  const {
    originalSegments,
    goalSegments,
    editSegments,
    viewingGoal,
    isEditing,
    isDirty,
    speakerOrder,
    reviewedSegs,
    totalSegments,
    hasGoal,
    loadStatus,
    saveStatus,
    error,
    editStats,
    reviewedSet,
    origIdSet,
    reviewPct,
    seekRef,
    editorRef,
    handlers,
  } = useTranscriptViewer(slug, visible, seekToTime)

  if (!visible) return null

  const isStreaming = loadStatus === 'streaming'
  const isLoaded = loadStatus === 'loaded'
  const hasError = loadStatus === 'error'

  if (isStreaming && originalSegments.length === 0) {
    return <InlineLoading description="Loading transcript…" />
  }
  if (hasError) {
    return <p className="pt-error">Error loading transcript: {error}</p>
  }

  const sourceSegments = viewingGoal ? goalSegments : originalSegments
  const displayReadSegs = sourceSegments.length > 50
    ? sourceSegments.filter(s => s.segment_type === 'content')
    : sourceSegments
  const turns = groupIntoTurns(displayReadSegs)

  return (
    <div className="purefoy-transcript-editor">
      <TranscriptToolbar
        hasGoal={hasGoal}
        viewingGoal={viewingGoal}
        isEditing={isEditing}
        isStreaming={isStreaming}
        isDirty={isDirty}
        saveStatus={saveStatus}
        editStats={editStats}
        reviewedCount={reviewedSegs.length}
        totalSegments={totalSegments}
        reviewPct={reviewPct}
        streamingCount={originalSegments.length}
        onToggleSource={handlers.toggleSource}
        onEnterEdit={handlers.enterEdit}
        onExitEdit={handlers.exitEdit}
        onSave={handlers.save}
        onDiscard={handlers.discard}
      />

      {isEditing && (
        <div className="pt-review-bar">
          <progress value={totalSegments > 0 ? reviewedSegs.length / totalSegments : 0} max={1} />
        </div>
      )}

      {!isEditing && isLoaded && (
        <ConversationView
          turns={turns}
          speakerOrder={speakerOrder}
          seekToTime={seekToTime}
          seekRef={seekRef}
          onEnterEdit={handlers.enterEdit}
        />
      )}

      {isEditing && (
        <EditGrid
          editSegments={editSegments}
          origIdSet={origIdSet}
          originalSegments={originalSegments}
          reviewedSet={reviewedSet}
          speakerOrder={speakerOrder}
          editorRef={editorRef}
          onSpeakerChange={handlers.speakerChange}
          onTextChange={handlers.textChange}
          onSplit={handlers.split}
        />
      )}
    </div>
  )
}
