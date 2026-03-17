import { useEffect } from 'react'
import {
  StructuredListWrapper, StructuredListHead, StructuredListRow,
  StructuredListCell, StructuredListBody, DataTableSkeleton,
  Breadcrumb, BreadcrumbItem, Tag, SkeletonText,
} from '@carbon/react'
import { useAppSelector, useAppDispatch } from '../store/hooks'
import { setSelectedTopicSlug, fetchTopicDetail } from '../store/slices/forumSlice'

export function ForumBrowser() {
  const dispatch = useAppDispatch()
  const topics = useAppSelector(s => s.forum.topics)
  const status = useAppSelector(s => s.forum.status)
  const selectedSlug = useAppSelector(s => s.forum.selectedTopicSlug)
  const selectedPosts = useAppSelector(s => s.forum.selectedTopicPosts)

  // Fetch topic detail when a slug is selected
  useEffect(() => {
    if (selectedSlug) {
      dispatch(fetchTopicDetail(selectedSlug))
    }
  }, [dispatch, selectedSlug])

  if (status === 'loading' && topics.length === 0) {
    return <DataTableSkeleton columnCount={3} rowCount={8} />
  }

  if (selectedSlug) {
    const topic = topics.find(t => t.slug === selectedSlug)
    return (
      <div className="purefoy-forum-topic">
        <Breadcrumb>
          <BreadcrumbItem onClick={() => dispatch(setSelectedTopicSlug(null))} isCurrentPage={false}>
            Forum
          </BreadcrumbItem>
          <BreadcrumbItem isCurrentPage>{topic?.title ?? selectedSlug}</BreadcrumbItem>
        </Breadcrumb>

        {topic && (
          <div className="purefoy-forum-topic__meta" style={{ margin: '0.5rem 0 1rem' }}>
            <Tag type="gray">{topic.replyCount} replies</Tag>
            <span style={{ marginLeft: '0.5rem', color: 'var(--cds-text-secondary)', fontSize: '0.75rem' }}>
              scraped {topic.scrapedAt.slice(0, 10)}
            </span>
          </div>
        )}

        {selectedPosts.length === 0 ? (
          <SkeletonText paragraph lineCount={4} />
        ) : (
          <div className="purefoy-forum-topic__posts">
            {selectedPosts.map(post => (
              <div key={post.postId} className="purefoy-forum-topic__post" style={{
                borderLeft: '3px solid var(--cds-border-subtle-01)',
                paddingLeft: '1rem',
                marginBottom: '1.5rem',
              }}>
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'baseline', marginBottom: '0.25rem' }}>
                  <strong style={{ fontSize: '0.875rem' }}>{post.author}</strong>
                  <span style={{ color: 'var(--cds-text-secondary)', fontSize: '0.75rem' }}>
                    {post.timestamp ? post.timestamp.slice(0, 16).replace('T', ' ') : ''}
                  </span>
                </div>
                <p style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{post.contentText}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }

  return (
    <StructuredListWrapper>
      <StructuredListHead>
        <StructuredListRow head>
          <StructuredListCell head>Topic</StructuredListCell>
          <StructuredListCell head>Replies</StructuredListCell>
          <StructuredListCell head>Scraped</StructuredListCell>
        </StructuredListRow>
      </StructuredListHead>
      <StructuredListBody>
        {topics.map(topic => (
          <StructuredListRow
            key={topic.slug}
            onClick={() => dispatch(setSelectedTopicSlug(topic.slug))}
            style={{ cursor: 'pointer' }}
          >
            <StructuredListCell>{topic.title}</StructuredListCell>
            <StructuredListCell>{topic.replyCount}</StructuredListCell>
            <StructuredListCell>{topic.scrapedAt.slice(0, 10)}</StructuredListCell>
          </StructuredListRow>
        ))}
      </StructuredListBody>
    </StructuredListWrapper>
  )
}
