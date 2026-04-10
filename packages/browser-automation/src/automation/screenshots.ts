/**
 * Screenshot Utilities
 */

import { Page } from 'playwright';
import { promises as fs } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { ViewportSize, ViewportPreset, getViewport, getViewportSuffix } from './viewport.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

function findProjectRoot(): string {
  let currentDir = __dirname;
  while (currentDir !== path.parse(currentDir).root) {
    try {
      const packageJsonPath = path.join(currentDir, 'package.json');
      if (require('fs').existsSync(packageJsonPath)) {
        const pkg = JSON.parse(require('fs').readFileSync(packageJsonPath, 'utf-8'));
        if (pkg.workspaces || (pkg.name === '@purefoy/browser-automation')) {
          if (pkg.name === '@purefoy/browser-automation') {
            return path.resolve(currentDir, '../..');
          }
          return currentDir;
        }
      }
    } catch {}
    currentDir = path.dirname(currentDir);
  }
  return path.resolve(__dirname, '../../..');
}

const PROJECT_ROOT = findProjectRoot();
const SCREENSHOTS_DIR = process.env.SCREENSHOTS_DIR
  ? path.isAbsolute(process.env.SCREENSHOTS_DIR)
    ? process.env.SCREENSHOTS_DIR
    : path.join(PROJECT_ROOT, process.env.SCREENSHOTS_DIR)
  : path.join(PROJECT_ROOT, 'temp/screenshots');

export type ImageFormat = 'png' | 'jpeg';

export interface ScreenshotOptions {
  name: string;
  fullPage?: boolean;
  selector?: string;
  path?: string;
  viewport?: ViewportPreset | ViewportSize;
  format?: ImageFormat;
  quality?: number;
}

export interface ScreenshotResult {
  success: boolean;
  path: string;
  filename: string;
  timestamp: string;
  url: string;
  viewport?: ViewportSize;
  format?: ImageFormat;
  fileSize?: number;
}

async function ensureScreenshotsDir(): Promise<void> {
  await fs.mkdir(SCREENSHOTS_DIR, { recursive: true });
}

async function createSessionDir(): Promise<string> {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
  const sessionDir = path.join(SCREENSHOTS_DIR, timestamp);
  await fs.mkdir(sessionDir, { recursive: true });
  return sessionDir;
}

export async function captureScreenshot(
  page: Page,
  options: ScreenshotOptions
): Promise<ScreenshotResult> {
  await ensureScreenshotsDir();

  let sessionDir: string;
  if (options.path) {
    sessionDir = path.isAbsolute(options.path)
      ? options.path
      : path.join(PROJECT_ROOT, options.path);
    await fs.mkdir(sessionDir, { recursive: true });
  } else {
    sessionDir = await createSessionDir();
  }

  const timestamp = new Date().toISOString();
  const format = options.format || 'png';
  const extension = format === 'jpeg' ? 'jpg' : 'png';
  const viewportSuffix = options.viewport ? getViewportSuffix(options.viewport) : '';
  const filename = `${options.name}${viewportSuffix}.${extension}`;
  const filepath = path.join(sessionDir, filename);

  let currentViewport: ViewportSize | undefined;
  if (options.viewport) {
    currentViewport = getViewport(options.viewport);
    await page.setViewportSize({
      width: currentViewport.width,
      height: currentViewport.height,
    });
  }

  const screenshotOpts: any = { path: filepath, type: format };
  if (format === 'jpeg' && options.quality !== undefined) {
    screenshotOpts.quality = Math.max(0, Math.min(100, options.quality));
  }

  if (options.fullPage || !options.selector) {
    screenshotOpts.fullPage = options.fullPage !== false;
    await page.screenshot(screenshotOpts);
  } else if (options.selector) {
    const element = page.locator(options.selector).first();
    const exists = (await element.count()) > 0;
    if (!exists) throw new Error(`Element not found: ${options.selector}`);
    await element.screenshot(screenshotOpts);
  }

  const stats = await fs.stat(filepath);

  return {
    success: true,
    path: filepath,
    filename,
    timestamp,
    url: page.url(),
    viewport: currentViewport,
    format,
    fileSize: stats.size,
  };
}

export async function listSessions(): Promise<string[]> {
  try {
    await ensureScreenshotsDir();
    const entries = await fs.readdir(SCREENSHOTS_DIR, { withFileTypes: true });
    return entries
      .filter((entry) => entry.isDirectory())
      .map((entry) => entry.name)
      .sort()
      .reverse();
  } catch {
    return [];
  }
}

export async function listScreenshotsInSession(sessionId: string): Promise<string[]> {
  try {
    const sessionDir = path.join(SCREENSHOTS_DIR, sessionId);
    const entries = await fs.readdir(sessionDir, { withFileTypes: true });
    return entries
      .filter((entry) => entry.isFile() && entry.name.endsWith('.png'))
      .map((entry) => entry.name);
  } catch {
    return [];
  }
}
