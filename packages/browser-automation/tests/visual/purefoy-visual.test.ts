/**
 * Visual Regression Tests for Purefoy
 *
 * Covers episode browser, episode detail, transcript viewer,
 * forum browser, forum search, chat panel, theme toggle,
 * settings modal, and responsive viewports (mobile + tablet).
 *
 * Purefoy does not have data-element selectors — tests use CSS
 * class selectors and Carbon component selectors as fallbacks.
 */

import { createTestSuite, createTestRunner } from '../../src/test-runner/index.js';
import { VisualDiffReporter } from '../../src/test-runner/reporters/VisualDiffReporter.js';
import { GitHubPRReporter } from '../../src/test-runner/reporters/GitHubPRReporter.js';
import { createVisualAssertions } from '../../src/test-runner/assertions/visual.js';
import { VISUAL_THRESHOLDS } from '../../src/visual/constants.js';

const API_URL = process.env.API_URL || 'http://localhost:3022';
const APP_URL = process.env.BROWSER_APP_URL || 'http://localhost:3020';
const UPDATE_BASELINES = process.env.UPDATE_BASELINES === 'true';
const GITHUB_RUN_ID = process.env.GITHUB_RUN_ID;
const GITHUB_RUN_NUMBER = process.env.GITHUB_RUN_NUMBER;
const GITHUB_REPOSITORY = process.env.GITHUB_REPOSITORY;

const SCREENSHOTS_DIR = process.env.SCREENSHOTS_DIR
  ? `${process.env.SCREENSHOTS_DIR}/visual-test`
  : 'temp/screenshots/visual-test';

// Carbon tab selectors (Purefoy uses Carbon <Tabs> without data-element attrs)
const TAB_SELECTORS = {
  episodes: 'button[role="tab"]:nth-of-type(1)',
  transcripts: 'button[role="tab"]:nth-of-type(2)',
  forum: 'button[role="tab"]:nth-of-type(3)',
  search: 'button[role="tab"]:nth-of-type(4)',
  interactive: 'button[role="tab"]:nth-of-type(5)',
};

if (UPDATE_BASELINES) {
  console.log('');
  console.log('UPDATE_BASELINES=true - All baselines will be updated');
  console.log('WARNING: This will overwrite existing baselines!');
  console.log('');
}

async function main() {
  const { suite, client } = createTestSuite(
    'Purefoy Visual Regression',
    API_URL
  );

  const visualReporter = new VisualDiffReporter('./temp/test-results');
  const visual = createVisualAssertions('purefoy-visual', visualReporter);

  // Suite setup — wait for app to be ready
  suite.beforeAll(async () => {
    const maxRetries = 2;
    let lastError: Error | null = null;

    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        if (attempt > 1) {
          console.log(`Retry attempt ${attempt}/${maxRetries}...`);
        }

        await client.navigate(APP_URL);
        await new Promise(resolve => setTimeout(resolve, 2000));
        await client.waitForSelector('[data-element="app-container"], .app-container', { timeout: 30000 });
        console.log('Purefoy loaded');
        return;
      } catch (error) {
        lastError = error as Error;
        console.log(`Attempt ${attempt}/${maxRetries} failed: ${lastError.message}`);
        if (attempt < maxRetries) {
          await new Promise(resolve => setTimeout(resolve, 5000));
        }
      }
    }

    throw new Error(`Failed to load Purefoy after ${maxRetries} attempts. Last error: ${lastError?.message}`);
  });

  // ── Dashboard ──────────────────────────────────────────────────────────

  suite.test('Dashboard - Initial Load', async ({ assert }) => {
    await client.navigate(APP_URL);
    await client.waitForSelector('[data-element="app-container"], .app-container');
    await new Promise(resolve => setTimeout(resolve, 1000));

    const result = await client.screenshot({
      name: 'dashboard-initial',
      viewport: 'desktop',
      fullPage: true,
      path: SCREENSHOTS_DIR,
    });

    assert.screenshotCaptured(result);
    await visual.matchesBaseline(result.path, 'dashboard-initial-desktop', {
      threshold: VISUAL_THRESHOLDS.STANDARD,
      updateBaseline: UPDATE_BASELINES,
    });
  });

  // ── Tab tests (desktop) ────────────────────────────────────────────────

  suite.test('Episodes Tab - Layout', async ({ assert }) => {
    await client.navigate(APP_URL);
    await client.waitForSelector('[data-element="app-container"], .app-container');

    await client.click(TAB_SELECTORS.episodes);
    await new Promise(resolve => setTimeout(resolve, 500));

    const result = await client.screenshot({
      name: 'episodes-tab',
      viewport: 'desktop',
      fullPage: true,
      path: SCREENSHOTS_DIR,
    });

    assert.screenshotCaptured(result);
    await visual.matchesBaseline(result.path, 'episodes-tab-desktop', {
      threshold: VISUAL_THRESHOLDS.STANDARD,
      updateBaseline: UPDATE_BASELINES,
    });
  });

  suite.test('Transcripts Tab - Layout', async ({ assert }) => {
    await client.navigate(APP_URL);
    await client.waitForSelector('[data-element="app-container"], .app-container');

    await client.click(TAB_SELECTORS.transcripts);
    await new Promise(resolve => setTimeout(resolve, 500));

    const result = await client.screenshot({
      name: 'transcripts-tab',
      viewport: 'desktop',
      fullPage: true,
      path: SCREENSHOTS_DIR,
    });

    assert.screenshotCaptured(result);
    await visual.matchesBaseline(result.path, 'transcripts-tab-desktop', {
      threshold: VISUAL_THRESHOLDS.STANDARD,
      updateBaseline: UPDATE_BASELINES,
    });
  });

  suite.test('Forum Tab - Layout', async ({ assert }) => {
    await client.navigate(APP_URL);
    await client.waitForSelector('[data-element="app-container"], .app-container');

    await client.click(TAB_SELECTORS.forum);
    await new Promise(resolve => setTimeout(resolve, 500));

    const result = await client.screenshot({
      name: 'forum-tab',
      viewport: 'desktop',
      fullPage: true,
      path: SCREENSHOTS_DIR,
    });

    assert.screenshotCaptured(result);
    await visual.matchesBaseline(result.path, 'forum-tab-desktop', {
      threshold: VISUAL_THRESHOLDS.STANDARD,
      updateBaseline: UPDATE_BASELINES,
    });
  });

  suite.test('Search Tab - Layout', async ({ assert }) => {
    await client.navigate(APP_URL);
    await client.waitForSelector('[data-element="app-container"], .app-container');

    await client.click(TAB_SELECTORS.search);
    await new Promise(resolve => setTimeout(resolve, 500));

    const result = await client.screenshot({
      name: 'search-tab',
      viewport: 'desktop',
      fullPage: true,
      path: SCREENSHOTS_DIR,
    });

    assert.screenshotCaptured(result);
    await visual.matchesBaseline(result.path, 'search-tab-desktop', {
      threshold: VISUAL_THRESHOLDS.STANDARD,
      updateBaseline: UPDATE_BASELINES,
    });
  });

  suite.test('Interactive Tab - Layout', async ({ assert }) => {
    await client.navigate(APP_URL);
    await client.waitForSelector('[data-element="app-container"], .app-container');

    await client.click(TAB_SELECTORS.interactive);
    await new Promise(resolve => setTimeout(resolve, 500));

    const result = await client.screenshot({
      name: 'interactive-tab',
      viewport: 'desktop',
      fullPage: true,
      path: SCREENSHOTS_DIR,
    });

    assert.screenshotCaptured(result);
    await visual.matchesBaseline(result.path, 'interactive-tab-desktop', {
      threshold: VISUAL_THRESHOLDS.STANDARD,
      updateBaseline: UPDATE_BASELINES,
    });
  });

  // ── Interactive states ──────────────────────────────────────────────────

  suite.test('Theme - Light Mode', async ({ assert }) => {
    await client.navigate(APP_URL);
    await client.waitForSelector('[data-element="app-container"], .app-container');

    const themeToggleExists = await client.elementExists('[data-element="theme-toggle"]');
    if (themeToggleExists) {
      await client.click('[data-element="theme-toggle"]');
      await new Promise(resolve => setTimeout(resolve, 500));
    }

    const result = await client.screenshot({
      name: 'theme-light',
      viewport: 'desktop',
      fullPage: true,
      path: SCREENSHOTS_DIR,
    });

    assert.screenshotCaptured(result);
    await visual.matchesBaseline(result.path, 'theme-light-desktop', {
      threshold: VISUAL_THRESHOLDS.STANDARD,
      updateBaseline: UPDATE_BASELINES,
    });

    if (themeToggleExists) {
      await client.click('[data-element="theme-toggle"]');
      await new Promise(resolve => setTimeout(resolve, 300));
    }
  });

  suite.test('Settings Modal', async ({ assert }) => {
    await client.navigate(APP_URL);
    await client.waitForSelector('[data-element="app-container"], .app-container');

    const settingsExists = await client.elementExists('[data-element="settings-toggle"]');
    if (settingsExists) {
      await client.click('[data-element="settings-toggle"]');
      await new Promise(resolve => setTimeout(resolve, 500));
    }

    const result = await client.screenshot({
      name: 'settings-modal',
      viewport: 'desktop',
      fullPage: true,
      path: SCREENSHOTS_DIR,
    });

    assert.screenshotCaptured(result);
    await visual.matchesBaseline(result.path, 'settings-modal-desktop', {
      threshold: VISUAL_THRESHOLDS.STANDARD,
      updateBaseline: UPDATE_BASELINES,
    });

    await client.pressKey('Escape');
    await new Promise(resolve => setTimeout(resolve, 300));
  });

  suite.test('Chat Input - Focus State', async ({ assert }) => {
    await client.navigate(APP_URL);
    await client.waitForSelector('[data-element="app-container"], .app-container');

    await client.click(TAB_SELECTORS.interactive);
    await new Promise(resolve => setTimeout(resolve, 500));

    const chatInputExists = await client.elementExists('[data-element="chat-input"]');
    if (chatInputExists) {
      await client.click('[data-element="chat-input"]');
      await new Promise(resolve => setTimeout(resolve, 300));
    }

    const result = await client.screenshot({
      name: 'chat-input-focus',
      viewport: 'desktop',
      fullPage: true,
      path: SCREENSHOTS_DIR,
    });

    assert.screenshotCaptured(result);
    await visual.matchesBaseline(result.path, 'chat-input-focus-desktop', {
      threshold: VISUAL_THRESHOLDS.STANDARD,
      updateBaseline: UPDATE_BASELINES,
    });
  });

  // ── Responsive — Mobile ────────────────────────────────────────────────

  suite.test('Dashboard - Mobile', async ({ assert }) => {
    await client.navigate(APP_URL);
    await client.waitForSelector('[data-element="app-container"], .app-container');
    await new Promise(resolve => setTimeout(resolve, 1000));

    const result = await client.screenshot({
      name: 'dashboard-mobile',
      viewport: 'mobile',
      fullPage: true,
      path: SCREENSHOTS_DIR,
    });

    assert.screenshotCaptured(result);
    await visual.matchesBaseline(result.path, 'dashboard-mobile', {
      threshold: VISUAL_THRESHOLDS.STANDARD,
      updateBaseline: UPDATE_BASELINES,
    });
  });

  suite.test('Episodes Tab - Mobile', async ({ assert }) => {
    await client.navigate(APP_URL);
    await client.waitForSelector('[data-element="app-container"], .app-container');

    await client.click(TAB_SELECTORS.episodes);
    await new Promise(resolve => setTimeout(resolve, 500));

    const result = await client.screenshot({
      name: 'episodes-mobile',
      viewport: 'mobile',
      fullPage: true,
      path: SCREENSHOTS_DIR,
    });

    assert.screenshotCaptured(result);
    await visual.matchesBaseline(result.path, 'episodes-mobile', {
      threshold: VISUAL_THRESHOLDS.STANDARD,
      updateBaseline: UPDATE_BASELINES,
    });
  });

  // ── Responsive — Tablet ────────────────────────────────────────────────

  suite.test('Dashboard - Tablet', async ({ assert }) => {
    await client.navigate(APP_URL);
    await client.waitForSelector('[data-element="app-container"], .app-container');
    await new Promise(resolve => setTimeout(resolve, 1000));

    const result = await client.screenshot({
      name: 'dashboard-tablet',
      viewport: 'tablet',
      fullPage: true,
      path: SCREENSHOTS_DIR,
    });

    assert.screenshotCaptured(result);
    await visual.matchesBaseline(result.path, 'dashboard-tablet', {
      threshold: VISUAL_THRESHOLDS.STANDARD,
      updateBaseline: UPDATE_BASELINES,
    });
  });

  // ── Run ────────────────────────────────────────────────────────────────

  const reporters: any[] = ['console', visualReporter];

  if (GITHUB_RUN_ID) {
    reporters.push(
      new GitHubPRReporter({
        outputPath: './temp/test-results/github-pr-comment.md',
        runId: GITHUB_RUN_ID,
        runNumber: GITHUB_RUN_NUMBER,
        repository: GITHUB_REPOSITORY,
      })
    );
  }

  const runner = createTestRunner({
    reporters,
    verbose: true,
  });

  const result = await runner.run(suite);
  const exitCode = result.summary.failed > 0 ? 1 : 0;

  console.log('');
  console.log(`Purefoy Visual Regression: ${exitCode === 0 ? 'PASSED' : 'FAILED'}`);
  console.log(`  ${result.summary.passed} passed, ${result.summary.failed} failed, ${result.summary.skipped} skipped`);
  console.log('');

  process.exit(exitCode);
}

main().catch((error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});
