import {
  DataTable,
  Table,
  TableHead,
  TableRow,
  TableHeader,
  TableBody,
  TableCell,
  DataTableSkeleton,
  InlineNotification,
  Button,
} from '@carbon/react'
import { useAppSelector, useAppDispatch } from '../store/hooks'
import { setSelectedSlug, fetchEpisodes } from '../store/slices/episodesSlice'
import { EpisodeDetail } from './EpisodeDetail'

export function EpisodeBrowser() {
  const dispatch = useAppDispatch()
  const status = useAppSelector(s => s.episodes.status)
  const items = useAppSelector(s => s.episodes.items)
  const total = useAppSelector(s => s.episodes.total)
  const hasMore = useAppSelector(s => s.episodes.hasMore)
  const currentPage = useAppSelector(s => s.episodes.filters.page)
  const selectedSlug = useAppSelector(s => s.episodes.selectedSlug)

  if (status === 'loading') {
    return <DataTableSkeleton columnCount={5} rowCount={10} />
  }

  if (status === 'error') {
    return (
      <InlineNotification
        kind="error"
        title="Failed to load episodes"
        subtitle="Check that purefoy-api is running on port 3021"
      />
    )
  }

  if (selectedSlug) {
    return (
      <EpisodeDetail
        slug={selectedSlug}
        onBack={() => dispatch(setSelectedSlug(null))}
      />
    )
  }

  const headers = [
    { key: 'episode', header: 'Ep.' },
    { key: 'title', header: 'Title' },
    { key: 'pubDate', header: 'Date' },
    { key: 'duration', header: 'Duration' },
    { key: 'hasTranscript', header: 'Transcript' },
  ]

  const rows = items.map(ep => ({
    id: ep.slug,
    episode: ep.episode != null ? `S${String(ep.season ?? 0).padStart(2, '0')}E${String(ep.episode).padStart(3, '0')}` : '—',
    title: ep.title,
    pubDate: ep.pubDate,
    duration: ep.duration,
    hasTranscript: ep.hasTranscript ? '✓' : '—',
  }))

  return (
    <>
      <p style={{ margin: '0 0 0.75rem', fontSize: '0.875rem', color: 'var(--cds-text-secondary)' }}>
        Showing {items.length} of {total} episodes
      </p>
      <DataTable rows={rows} headers={headers}>
        {({ rows: tableRows, headers: tableHeaders, getTableProps, getHeaderProps, getRowProps }) => (
          <Table {...getTableProps()}>
            <TableHead>
              <TableRow>
                {tableHeaders.map(header => (
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  <TableHeader {...getHeaderProps({ header } as any)} key={header.key}>
                    {header.header}
                  </TableHeader>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {tableRows.map(row => (
                <TableRow
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  {...getRowProps({ row } as any)}
                  key={row.id}
                  onClick={() => dispatch(setSelectedSlug(row.id))}
                  style={{ cursor: 'pointer' }}
                >
                  {row.cells.map(cell => (
                    <TableCell key={cell.id}>{cell.value}</TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </DataTable>
      {hasMore && (
        <div style={{ marginTop: '1rem', textAlign: 'center' }}>
          <Button
            kind="ghost"
            size="sm"
            onClick={() => dispatch(fetchEpisodes({ page: currentPage + 1, limit: 500 }))}
          >
            {`Load more (${total - items.length} remaining)`}
          </Button>
        </div>
      )}
    </>
  )
}
