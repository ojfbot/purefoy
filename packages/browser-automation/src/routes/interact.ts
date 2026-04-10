/**
 * Interaction Routes
 */

import { Router, Request, Response } from 'express';
import { browserManager } from '../automation/browser.js';
import {
  clickElement,
  typeIntoElement,
  hoverOverElement,
  fillElement,
  pressKey,
  selectOption,
  setChecked,
  ClickOptions,
  TypeOptions,
  HoverOptions,
} from '../automation/actions.js';

const router: Router = Router();

router.post('/interact/click', async (req: Request, res: Response) => {
  try {
    const { selector, options }: { selector: string; options?: ClickOptions } = req.body;
    if (!selector) {
      res.status(400).json({ success: false, error: 'Selector is required' });
      return;
    }
    const page = await browserManager.getPage();
    const result = await clickElement(page, selector, options);
    if (!result.success) {
      res.status(result.elementFound ? 500 : 404).json(result);
      return;
    }
    res.json(result);
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Click operation failed',
    });
  }
});

router.post('/interact/type', async (req: Request, res: Response) => {
  try {
    const { selector, text, options }: { selector: string; text: string; options?: TypeOptions } =
      req.body;
    if (!selector || text === undefined) {
      res.status(400).json({ success: false, error: 'Selector and text are required' });
      return;
    }
    const page = await browserManager.getPage();
    const result = await typeIntoElement(page, selector, text, options);
    if (!result.success) {
      res.status(result.elementFound ? 500 : 404).json(result);
      return;
    }
    res.json(result);
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Type operation failed',
    });
  }
});

router.post('/interact/fill', async (req: Request, res: Response) => {
  try {
    const { selector, text, timeout }: { selector: string; text: string; timeout?: number } =
      req.body;
    if (!selector || text === undefined) {
      res.status(400).json({ success: false, error: 'Selector and text are required' });
      return;
    }
    const page = await browserManager.getPage();
    const result = await fillElement(page, selector, text, { timeout });
    if (!result.success) {
      res.status(result.elementFound ? 500 : 404).json(result);
      return;
    }
    res.json(result);
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Fill operation failed',
    });
  }
});

router.post('/interact/hover', async (req: Request, res: Response) => {
  try {
    const { selector, options }: { selector: string; options?: HoverOptions } = req.body;
    if (!selector) {
      res.status(400).json({ success: false, error: 'Selector is required' });
      return;
    }
    const page = await browserManager.getPage();
    const result = await hoverOverElement(page, selector, options);
    if (!result.success) {
      res.status(result.elementFound ? 500 : 404).json(result);
      return;
    }
    res.json(result);
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Hover operation failed',
    });
  }
});

router.post('/interact/press', async (req: Request, res: Response) => {
  try {
    const { key, delay }: { key: string; delay?: number } = req.body;
    if (!key) {
      res.status(400).json({ success: false, error: 'Key is required' });
      return;
    }
    const page = await browserManager.getPage();
    const result = await pressKey(page, key, { delay });
    res.json(result);
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Press key operation failed',
    });
  }
});

router.post('/interact/select', async (req: Request, res: Response) => {
  try {
    const { selector, value, timeout }: { selector: string; value: string | string[]; timeout?: number } = req.body;
    if (!selector || value === undefined) {
      res.status(400).json({ success: false, error: 'Selector and value are required' });
      return;
    }
    const page = await browserManager.getPage();
    const result = await selectOption(page, selector, value, { timeout });
    if (!result.success) {
      res.status(result.elementFound ? 500 : 404).json(result);
      return;
    }
    res.json(result);
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Select operation failed',
    });
  }
});

router.post('/interact/check', async (req: Request, res: Response) => {
  try {
    const { selector, checked, timeout, force }: { selector: string; checked: boolean; timeout?: number; force?: boolean } = req.body;
    if (!selector || checked === undefined) {
      res.status(400).json({ success: false, error: 'Selector and checked state are required' });
      return;
    }
    const page = await browserManager.getPage();
    const result = await setChecked(page, selector, checked, { timeout, force });
    if (!result.success) {
      res.status(result.elementFound ? 500 : 404).json(result);
      return;
    }
    res.json(result);
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Check operation failed',
    });
  }
});

export default router;
