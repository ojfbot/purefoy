/**
 * Element Query Routes
 */

import { Router, Request, Response } from 'express';
import { browserManager } from '../automation/browser.js';

const router: Router = Router();

router.get('/element/exists', async (req: Request, res: Response) => {
  try {
    const { selector, text, role } = req.query;
    if (!selector && !text && !role) {
      res.status(400).json({ success: false, error: 'At least one query parameter required' });
      return;
    }
    const page = await browserManager.getPage();
    let exists = false, visible = false, enabled = false, count = 0;

    if (selector && typeof selector === 'string') {
      const elements = await page.locator(selector).all();
      count = elements.length;
      exists = count > 0;
      if (exists) {
        const first = page.locator(selector).first();
        visible = await first.isVisible().catch(() => false);
        enabled = await first.isEnabled().catch(() => false);
      }
    } else if (text && typeof text === 'string') {
      const elements = await page.getByText(text).all();
      count = elements.length;
      exists = count > 0;
      if (exists) {
        const first = page.getByText(text).first();
        visible = await first.isVisible().catch(() => false);
        enabled = await first.isEnabled().catch(() => false);
      }
    } else if (role && typeof role === 'string') {
      const elements = await page.getByRole(role as any).all();
      count = elements.length;
      exists = count > 0;
      if (exists) {
        const first = page.getByRole(role as any).first();
        visible = await first.isVisible().catch(() => false);
        enabled = await first.isEnabled().catch(() => false);
      }
    }
    res.json({ success: true, exists, visible, enabled, count, query: { selector, text, role } });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Element query failed',
    });
  }
});

router.get('/element/text', async (req: Request, res: Response) => {
  try {
    const { selector } = req.query;
    if (!selector || typeof selector !== 'string') {
      res.status(400).json({ success: false, error: 'selector query parameter is required' });
      return;
    }
    const page = await browserManager.getPage();
    const element = page.locator(selector).first();
    const exists = (await element.count()) > 0;
    if (!exists) {
      res.status(404).json({ success: false, error: 'Element not found' });
      return;
    }
    const text = await element.textContent();
    res.json({ success: true, text: text || '', selector });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Failed to get text',
    });
  }
});

router.get('/element/attribute', async (req: Request, res: Response) => {
  try {
    const { selector, attribute } = req.query;
    if (!selector || typeof selector !== 'string') {
      res.status(400).json({ success: false, error: 'selector required' });
      return;
    }
    if (!attribute || typeof attribute !== 'string') {
      res.status(400).json({ success: false, error: 'attribute required' });
      return;
    }
    const page = await browserManager.getPage();
    const element = page.locator(selector).first();
    const exists = (await element.count()) > 0;
    if (!exists) {
      res.status(404).json({ success: false, error: 'Element not found' });
      return;
    }
    const value = await element.getAttribute(attribute);
    res.json({ success: true, value, selector, attribute });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Failed to get attribute',
    });
  }
});

router.get('/page/title', async (_req: Request, res: Response) => {
  try {
    const page = await browserManager.getPage();
    const title = await page.evaluate(() => document.title);
    res.json({ success: true, title });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Failed to get page title',
    });
  }
});

router.get('/element/has-focus', async (req: Request, res: Response) => {
  try {
    const { selector } = req.query;
    if (!selector || typeof selector !== 'string') {
      res.status(400).json({ success: false, error: 'selector required' });
      return;
    }
    const page = await browserManager.getPage();
    const hasFocus = await page.evaluate((sel) => {
      const element = document.querySelector(sel);
      return document.activeElement === element && element !== null;
    }, selector);
    res.json({ success: true, hasFocus, selector });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Failed to check focus',
    });
  }
});

export default router;
