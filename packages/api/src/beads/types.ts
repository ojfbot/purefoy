/**
 * PurefoyBeadLike — FrameBeadLike shape for Purefoy episodes.
 *
 * Satisfies the FrameBeadLike contract defined in ADR-0016 (core repo).
 * Deliberately not imported from @core/workflows to avoid cross-repo coupling.
 *
 * Prefix: "pure-"
 * sourceApp: "purefoy"
 */

export type PurefoyBeadStatus = 'created' | 'live' | 'closed' | 'archived';

export interface PurefoyBead {
  id: string;
  type: 'task';
  status: PurefoyBeadStatus;
  sourceApp: 'purefoy';
  created_at: string;
  updated_at: string;
  payload: {
    slug: string;
    title: string;
    season: number;
    episode: number;
    hasTranscript: boolean;
    hasGoal: boolean;
    reviewCoverage: number;
  };
}
