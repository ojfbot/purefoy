/**
 * Screenshot Capture Routes
 */

import { Router, Request, Response } from 'express';
import { browserManager } from '../automation/browser.js';
import { captureScreenshot, listSessions, listScreenshotsInSession, ImageFormat } from '../automation/screenshots.js';
import { ViewportPreset, ViewportSize } from '../automation/viewport.js';

const router: Router = Router();

router.post('/screenshot', async (req: Request, res: Response) => {
  try {
    const { name, fullPage = true, selector, sessionDir, path: pathOption, viewport, format, quality }: {
      name: string;
      fullPage?: boolean;
      selector?: string;
      sessionDir?: string;
      path?: string;
      viewport?: ViewportPreset | ViewportSize;
      format?: ImageFormat;
      quality?: number;
    } = req.body;

    if (!name) {
      res.status(400).json({ success: false, error: 'Screenshot name is required' });
      return;
    }

    const page = await browserManager.getPage();
    const currentUrl = page.url();
    if (!currentUrl || currentUrl === 'about:blank') {
      res.status(400).json({ success: false, error: 'Navigate to a page first' });
      return;
    }

    const result = await captureScreenshot(page, {
      name,
      fullPage,
      selector,
      path: sessionDir ?? pathOption,
      viewport,
      format,
      quality,
    });
    res.json(result);
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Screenshot capture failed',
    });
  }
});

router.get('/screenshot/sessions', async (_req: Request, res: Response) => {
  try {
    const sessions = await listSessions();
    res.json({ success: true, sessions, count: sessions.length });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Failed to list sessions',
    });
  }
});

router.get('/screenshot/sessions/:sessionId', async (req: Request, res: Response) => {
  try {
    const { sessionId } = req.params;
    const screenshots = await listScreenshotsInSession(sessionId);
    res.json({ success: true, sessionId, screenshots, count: screenshots.length });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Failed to list screenshots',
    });
  }
});

export default router;
