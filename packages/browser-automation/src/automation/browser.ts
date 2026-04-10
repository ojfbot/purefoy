/**
 * Browser Instance Manager
 *
 * Manages Playwright browser lifecycle with singleton pattern.
 * Handles browser launch, page creation, and cleanup.
 */

import { Browser, BrowserContext, Page, chromium } from 'playwright';

const HEADLESS = process.env.HEADLESS === 'true';
const BROWSER_APP_URL = process.env.BROWSER_APP_URL || 'http://localhost:3020';
const SESSION_TIMEOUT_MS = 5 * 60 * 1000; // 5 minutes

interface Session {
  id: string;
  createdAt: Date;
  lastActivity: Date;
  url: string;
}

class BrowserManager {
  private browser: Browser | null = null;
  private context: BrowserContext | null = null;
  private page: Page | null = null;
  private currentSession: Session | null = null;
  private sessionCleanupTimer: NodeJS.Timeout | null = null;

  /**
   * Launch browser instance if not already running
   */
  async launch(): Promise<void> {
    if (this.browser) {
      console.log('Browser already running');
      return;
    }

    console.log('Launching browser...');
    console.log(`  Headless: ${HEADLESS}`);
    console.log(`  Target: ${BROWSER_APP_URL}`);

    this.browser = await chromium.launch({
      headless: HEADLESS,
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
      ],
    });

    this.context = await this.browser.newContext({
      viewport: { width: 1920, height: 1080 },
      userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Purefoy-Automation',
    });

    // Inject Redux DevTools emulation for store access
    await this.context.addInitScript(() => {
      (window as any).__REDUX_DEVTOOLS_EXTENSION__ = {
        stores: [],
      };
    });

    this.page = await this.context.newPage();
    console.log('Browser launched successfully');
  }

  /**
   * Get current page instance (launches browser if needed)
   */
  async getPage(): Promise<Page> {
    if (!this.page) {
      await this.launch();
      this.startSession();
    }
    this.updateSessionActivity();
    return this.page!;
  }

  private startSession(): void {
    const sessionId = `session-${Date.now()}`;
    this.currentSession = {
      id: sessionId,
      createdAt: new Date(),
      lastActivity: new Date(),
      url: this.page?.url() || 'about:blank',
    };
    console.log(`Started session: ${sessionId}`);
    this.scheduleSessionCleanup();
  }

  private updateSessionActivity(): void {
    if (this.currentSession) {
      this.currentSession.lastActivity = new Date();
      this.currentSession.url = this.page?.url() || 'about:blank';
      this.scheduleSessionCleanup();
    }
  }

  private scheduleSessionCleanup(): void {
    if (this.sessionCleanupTimer) {
      clearTimeout(this.sessionCleanupTimer);
    }
    this.sessionCleanupTimer = setTimeout(async () => {
      if (this.currentSession) {
        const inactiveTime = Date.now() - this.currentSession.lastActivity.getTime();
        if (inactiveTime >= SESSION_TIMEOUT_MS) {
          console.log(`Session ${this.currentSession.id} timed out`);
          await this.endSession();
        }
      }
    }, SESSION_TIMEOUT_MS);
  }

  private async endSession(): Promise<void> {
    if (!this.currentSession) return;
    console.log(`Ending session: ${this.currentSession.id}`);
    if (this.sessionCleanupTimer) {
      clearTimeout(this.sessionCleanupTimer);
      this.sessionCleanupTimer = null;
    }
    this.currentSession = null;
    await this.close();
  }

  isRunning(): boolean {
    return this.browser !== null && this.browser.isConnected();
  }

  async close(): Promise<void> {
    if (!this.browser) return;
    console.log('Closing browser...');
    try {
      if (this.page) {
        await this.page.close();
        this.page = null;
      }
      if (this.context) {
        await this.context.close();
        this.context = null;
      }
      await this.browser.close();
      this.browser = null;
      console.log('Browser closed successfully');
    } catch (error) {
      console.error('Error closing browser:', error);
      this.browser = null;
      this.context = null;
      this.page = null;
    }
  }

  getCurrentUrl(): string | null {
    return this.page?.url() || null;
  }

  getStatus(): {
    running: boolean;
    currentUrl: string | null;
    connected: boolean;
    session: Session | null;
  } {
    return {
      running: this.isRunning(),
      currentUrl: this.getCurrentUrl(),
      connected: this.browser?.isConnected() || false,
      session: this.currentSession,
    };
  }

  async clearStorage(): Promise<void> {
    if (!this.context || !this.page) {
      throw new Error('Cannot clear storage - no browser context available');
    }
    console.log('Clearing browser storage...');
    await this.context.clearCookies();
    await this.page.evaluate(async () => {
      localStorage.clear();
      sessionStorage.clear();
    });
    console.log('Browser storage cleared');
  }

  async resetContext(): Promise<void> {
    if (!this.browser) {
      throw new Error('Cannot reset context - no browser available');
    }
    console.log('Resetting browser context...');
    if (this.page) {
      await this.page.close();
      this.page = null;
    }
    if (this.context) {
      await this.context.close();
      this.context = null;
    }
    this.context = await this.browser.newContext({
      viewport: { width: 1920, height: 1080 },
      userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Purefoy-Automation',
    });
    await this.context.addInitScript(() => {
      (window as any).__REDUX_DEVTOOLS_EXTENSION__ = {
        stores: [],
      };
    });
    this.page = await this.context.newPage();
    console.log('Browser context reset successfully');
  }
}

// Singleton instance
export const browserManager = new BrowserManager();

// Cleanup on process termination
process.on('SIGTERM', async () => {
  await browserManager.close();
});

process.on('SIGINT', async () => {
  await browserManager.close();
});
