import type { EpisodeListItem } from '../types.js';
import type { PurefoyBead, PurefoyBeadStatus } from './types.js';

function deriveStatus(episode: EpisodeListItem): PurefoyBeadStatus {
  if (episode.hasGoal && episode.reviewCoverage >= 1) return 'closed';
  if (episode.hasTranscript) return 'live';
  return 'created';
}

export function mapEpisodeToBead(episode: EpisodeListItem): PurefoyBead {
  return {
    id: `pure-${episode.slug}`,
    type: 'task',
    status: deriveStatus(episode),
    sourceApp: 'purefoy',
    created_at: episode.pubDate ?? new Date().toISOString(),
    updated_at: new Date().toISOString(),
    payload: {
      slug: episode.slug,
      title: episode.title,
      season: episode.season ?? 0,
      episode: episode.episode ?? 0,
      hasTranscript: episode.hasTranscript,
      hasGoal: episode.hasGoal,
      reviewCoverage: episode.reviewCoverage,
    },
  };
}
