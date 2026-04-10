/**
 * Waiting Strategy Routes
 */

import { Router, Request, Response } from 'express';
import { browserManager } from '../automation/browser.js';

const router: Router = Router();

type WaitCondition = 'selector' | 'text' | 'network' | 'timeout' | 'url' | 'function';

router.post('/wait', async (req: Request, res: Response) => {
  try {
    const { condition, value, timeout = 30000, state = 'visible' }: {
      condition: WaitCondition;
      value?: string;
      timeout?: number;
      state?: 'attached' | 'detached' | 'visible' | 'hidden';
    } = req.body;

    if (!condition) {
      res.status(400).json({ success: false, error: 'Condition is required' });
      return;
    }

    const page = await browserManager.getPage();
    const startTime = Date.now();

    try {
      switch (condition) {
        case 'selector':
          if (!value) { res.status(400).json({ success: false, error: 'Selector value required' }); return; }
          await page.waitForSelector(value, { state, timeout });
          break;
        case 'text':
          if (!value) { res.status(400).json({ success: false, error: 'Text value required' }); return; }
          await page.locator(`text=${value}`).waitFor({ state, timeout });
          break;
        case 'network':
          await page.waitForLoadState('networkidle', { timeout });
          break;
        case 'timeout': {
          const waitTime = value ? parseInt(value, 10) : timeout;
          await page.waitForTimeout(waitTime);
          break;
        }
        case 'url':
          if (!value) { res.status(400).json({ success: false, error: 'URL pattern required' }); return; }
          await page.waitForURL(value, { timeout });
          break;
        case 'function':
          if (!value) { res.status(400).json({ success: false, error: 'Function expression required' }); return; }
          await page.waitForFunction(value, { timeout });
          break;
        default:
          res.status(400).json({ success: false, error: `Unknown condition: ${condition}` });
          return;
      }
      res.json({ success: true, timeElapsed: Date.now() - startTime });
    } catch (waitError) {
      res.status(408).json({
        success: false,
        timeElapsed: Date.now() - startTime,
        error: waitError instanceof Error ? waitError.message : 'Wait condition failed',
      });
    }
  } catch (error) {
    res.status(500).json({
      success: false,
      timeElapsed: 0,
      error: error instanceof Error ? error.message : 'Wait operation failed',
    });
  }
});

router.post('/wait/load', async (req: Request, res: Response) => {
  try {
    const { state = 'load', timeout = 30000 }: { state?: 'load' | 'domcontentloaded' | 'networkidle'; timeout?: number } = req.body;
    const page = await browserManager.getPage();
    const startTime = Date.now();
    await page.waitForLoadState(state, { timeout });
    res.json({ success: true, timeElapsed: Date.now() - startTime, state });
  } catch (error) {
    res.status(408).json({
      success: false,
      timeElapsed: 0,
      error: error instanceof Error ? error.message : 'Wait for load state failed',
    });
  }
});

router.post('/wait/element', async (req: Request, res: Response) => {
  try {
    const { selector, state = 'visible', timeout = 30000 }: {
      selector: string;
      state?: 'attached' | 'detached' | 'visible' | 'hidden';
      timeout?: number;
    } = req.body;

    if (!selector) {
      res.status(400).json({ success: false, error: 'Selector is required' });
      return;
    }

    const page = await browserManager.getPage();
    const startTime = Date.now();
    const element = page.locator(selector).first();
    await element.waitFor({ state, timeout });
    res.json({ success: true, timeElapsed: Date.now() - startTime, selector, state });
  } catch (error) {
    res.status(408).json({
      success: false,
      timeElapsed: 0,
      error: error instanceof Error ? error.message : 'Element wait failed',
    });
  }
});

export default router;
