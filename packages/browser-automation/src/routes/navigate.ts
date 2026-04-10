/**
 * Navigation Routes
 */

import { Router, Request, Response } from 'express';
import { browserManager } from '../automation/browser.js';

const router: Router = Router();

interface NavigateRequest {
  url: string;
  waitFor?: 'load' | 'networkidle' | 'domcontentloaded';
  timeout?: number;
}

router.post('/navigate', async (req: Request, res: Response) => {
  try {
    const { url, waitFor = 'load', timeout = 30000 }: NavigateRequest = req.body;
    if (!url) {
      res.status(400).json({ success: false, error: 'URL is required' });
      return;
    }
    const page = await browserManager.getPage();
    await page.goto(url, { waitUntil: waitFor, timeout });
    const currentUrl = page.url();
    res.json({ success: true, currentUrl, title: await page.title() });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Navigation failed',
    });
  }
});

router.get('/navigate/current', async (_req: Request, res: Response) => {
  try {
    const status = browserManager.getStatus();
    if (!status.running) {
      res.status(400).json({ success: false, error: 'Browser not running' });
      return;
    }
    const page = await browserManager.getPage();
    res.json({ success: true, currentUrl: page.url(), title: await page.title() });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Failed to get current URL',
    });
  }
});

router.post('/navigate/back', async (_req: Request, res: Response) => {
  try {
    const page = await browserManager.getPage();
    await page.goBack({ waitUntil: 'load' });
    res.json({ success: true, currentUrl: page.url() });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Failed to navigate back',
    });
  }
});

router.post('/navigate/reload', async (_req: Request, res: Response) => {
  try {
    const page = await browserManager.getPage();
    await page.reload({ waitUntil: 'load' });
    res.json({ success: true, currentUrl: page.url() });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Failed to reload page',
    });
  }
});

export default router;
