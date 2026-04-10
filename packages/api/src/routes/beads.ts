import { Router, type IRouter, type Request, type Response } from 'express';
import { episodeCache } from '../services/episode-cache.js';
import { mapEpisodeToBead } from '../beads/mapper.js';
import type { PurefoyBeadStatus } from '../beads/types.js';

export const beadsRouter: IRouter = Router();

/**
 * GET /api/beads
 *
 * Returns all episodes mapped to the FrameBeadLike shape (ADR-0016).
 * Read-only projection — Mayor/frame-agent aggregation endpoint.
 *
 * Query params:
 *   status — filter by bead status: "created" | "live" | "closed" | "archived"
 */
beadsRouter.get('/', (req: Request, res: Response) => {
  const episodes = episodeCache.getAll();
  let beads = episodes.map(mapEpisodeToBead);

  const statusParam = req.query.status as string | undefined;
  if (statusParam) {
    const valid: PurefoyBeadStatus[] = ['created', 'live', 'closed', 'archived'];
    if (!valid.includes(statusParam as PurefoyBeadStatus)) {
      res.status(400).json({ error: `Invalid status. Must be one of: ${valid.join(', ')}` });
      return;
    }
    beads = beads.filter(b => b.status === statusParam);
  }

  res.json({ beads, count: beads.length });
});
