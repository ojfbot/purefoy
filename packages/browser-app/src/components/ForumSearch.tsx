import { useState } from 'react'
import { Search, Button, StructuredListWrapper, StructuredListBody, StructuredListRow, StructuredListCell } from '@carbon/react'
import { useAppDispatch, useAppSelector } from '../store/hooks'
import { searchForum, setSearchQuery } from '../store/slices/forumSlice'

// TODO: implement — debounced search input, render FTS5 results with snippet highlighting
export function ForumSearch() {
  const dispatch = useAppDispatch()
  const query = useAppSelector(s => s.forum.searchQuery)
  const results = useAppSelector(s => s.forum.searchResults)
  const status = useAppSelector(s => s.forum.status)
  const [localQuery, setLocalQuery] = useState(query)

  const handleSearch = () => {
    if (!localQuery.trim()) return
    dispatch(setSearchQuery(localQuery))
    dispatch(searchForum(localQuery))
  }

  return (
    <div className="purefoy-forum-search">
      <div className="purefoy-forum-search__input-row">
        <Search
          id="forum-search-input"
          labelText="Search forum posts"
          placeholder="e.g. natural lighting, handheld, Sicario"
          value={localQuery}
          onChange={e => setLocalQuery(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') handleSearch() }}
        />
        <Button onClick={handleSearch} disabled={status === 'loading'}>Search</Button>
      </div>

      {results.length > 0 && (
        <StructuredListWrapper>
          <StructuredListBody>
            {results.map(r => (
              <StructuredListRow key={r.postId}>
                <StructuredListCell>
                  <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'baseline', marginBottom: '0.25rem' }}>
                    <strong style={{ fontSize: '0.875rem' }}>{r.author}</strong>
                    <span style={{ color: 'var(--cds-text-secondary)', fontSize: '0.75rem' }}>
                      {r.timestamp?.slice(0, 10) ?? '—'}
                    </span>
                    <span style={{ color: 'var(--cds-text-secondary)', fontSize: '0.75rem' }}>
                      {r.topicSlug}
                    </span>
                  </div>
                  {/* FTS5 snippet() wraps matches in <mark> tags — safe server-generated HTML */}
                  <p
                    style={{ margin: 0, fontSize: '0.875rem' }}
                    dangerouslySetInnerHTML={{ __html: r.snippet }}
                  />
                </StructuredListCell>
              </StructuredListRow>
            ))}
          </StructuredListBody>
        </StructuredListWrapper>
      )}

      {results.length === 0 && query && status !== 'loading' && (
        <p style={{ color: 'var(--cds-text-secondary)' }}>No results for "{query}"</p>
      )}
    </div>
  )
}
