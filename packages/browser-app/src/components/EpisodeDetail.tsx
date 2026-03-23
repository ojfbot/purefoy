import { useEffect, useState } from 'react'
import { Breadcrumb, BreadcrumbItem, Button, Tag, SkeletonText } from '@carbon/react'
import { useAppDispatch, useAppSelector } from '../store/hooks'
import { fetchEpisodeDetail, fetchChapters } from '../store/slices/episodesSlice'
import { TranscriptViewer } from './TranscriptViewer'
import type { ChapterResult } from '../types'

interface EpisodeDetailProps {
  slug: string
  onBack: () => void
}

export function EpisodeDetail({ slug, onBack }: EpisodeDetailProps) {
  const dispatch = useAppDispatch()
  const detail = useAppSelector(s => s.episodes.detail)
  const chapters = useAppSelector(s => s.episodes.chapters)
  const status = useAppSelector(s => s.episodes.status)

  const [transcriptVisible, setTranscriptVisible] = useState(false)
  const [seekToTime, setSeekToTime] = useState<number | undefined>(undefined)

  useEffect(() => {
    dispatch(fetchEpisodeDetail(slug))
    dispatch(fetchChapters(slug))
  }, [dispatch, slug])

  const handleChapterClick = (startTimeSec: number) => {
    setTranscriptVisible(true)
    setSeekToTime(startTimeSec)
  }

  if (status === 'loading' || !detail) {
    return <SkeletonText paragraph lineCount={6} />
  }

  return (
    <div className="purefoy-episode-detail">
      <Breadcrumb>
        <BreadcrumbItem onClick={onBack} isCurrentPage={false}>Episodes</BreadcrumbItem>
        <BreadcrumbItem isCurrentPage>{detail.title}</BreadcrumbItem>
      </Breadcrumb>

      <div className="purefoy-episode-detail__meta">
        <p>{detail.pubDate} · {detail.duration}</p>
        {detail.stats && (
          <div className="purefoy-episode-detail__tags">
            {detail.stats.topics.map(t => <Tag key={t} type="blue">{t}</Tag>)}
            {detail.stats.films.map(f => <Tag key={f} type="green">{f}</Tag>)}
          </div>
        )}
      </div>

      {chapters.length > 0 && (
        <div className="purefoy-episode-detail__chapters">
          <h3>Chapters ({chapters.length})</h3>
          <ul style={{ listStyle: 'none', padding: 0 }}>
            {(chapters as ChapterResult[]).map(ch => (
              <li
                key={ch.index}
                onClick={() => handleChapterClick(ch.start_time)}
                style={{ cursor: 'pointer', padding: '0.25rem 0', borderBottom: '1px solid var(--cds-border-subtle-01)' }}
              >
                <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem' }}>
                  <strong>{ch.title}</strong>
                  <span style={{ color: 'var(--cds-text-secondary)', fontSize: '0.75rem' }}>
                    {Math.floor(ch.start_time / 60)}:{String(Math.floor(ch.start_time % 60)).padStart(2, '0')}
                  </span>
                </div>
                {ch.summary && (
                  <p style={{ margin: '0.125rem 0 0', fontSize: '0.75rem', color: 'var(--cds-text-secondary)' }}>
                    {ch.summary}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      <Button
        kind="ghost"
        size="sm"
        onClick={() => setTranscriptVisible(v => !v)}
        style={{ marginTop: '1rem' }}
      >
        {transcriptVisible ? 'Hide Transcript' : 'View Transcript'}
        {!transcriptVisible && detail.hasGoal && (
          <Tag size="sm" type="green" style={{ marginLeft: '0.5rem' }}>Goal</Tag>
        )}
      </Button>

      <TranscriptViewer slug={slug} visible={transcriptVisible} seekToTime={seekToTime} />
    </div>
  )
}
