/**
 * Browser Automation Service
 *
 * Provides REST API for browser automation using Playwright.
 * Enables AI dev tools to interact with the UI, capture screenshots,
 * and test component presence.
 */

import express, { Request, Response } from 'express';
import cors from 'cors';
import navigateRoutes from './routes/navigate.js';
import queryRoutes from './routes/query.js';
import captureRoutes from './routes/capture.js';
import interactRoutes from './routes/interact.js';
import waitRoutes from './routes/wait.js';
import { browserManager } from './automation/browser.js';

const app = express();
const PORT = process.env.PORT || 3022;
const NODE_ENV = process.env.NODE_ENV || 'development';
const BROWSER_APP_URL = process.env.BROWSER_APP_URL || 'http://localhost:3020';
const HEADLESS = process.env.HEADLESS === 'true';

// Middleware
app.use(cors());
app.use(express.json());

// Request logging middleware
app.use((req, _res, next) => {
  const timestamp = new Date().toISOString();
  console.log(`[${timestamp}] ${req.method} ${req.path}`);
  next();
});

// API Routes
app.use('/api', navigateRoutes);
app.use('/api', queryRoutes);
app.use('/api', captureRoutes);
app.use('/api', interactRoutes);
app.use('/api', waitRoutes);

/**
 * Health check endpoint
 */
app.get('/health', async (_req: Request, res: Response) => {
  const browserStatus = browserManager.getStatus();

  res.status(200).json({
    status: browserStatus.running ? 'ready' : 'idle',
    service: 'browser-automation',
    version: '0.1.0',
    environment: NODE_ENV,
    browser: browserStatus,
    config: {
      browserAppUrl: BROWSER_APP_URL,
      headless: HEADLESS,
      port: PORT,
    },
    timestamp: new Date().toISOString(),
  });
});

/**
 * Close browser endpoint
 */
app.post('/api/close', async (_req: Request, res: Response) => {
  try {
    await browserManager.close();
    res.status(200).json({
      success: true,
      message: 'Browser closed successfully',
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    console.error('Error closing browser:', error);
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
});

/**
 * Clear browser storage endpoint
 */
app.post('/api/storage/clear', async (_req: Request, res: Response): Promise<void> => {
  const allowedEnvs = ['development', 'test'];
  if (!allowedEnvs.includes(NODE_ENV)) {
    res.status(403).json({
      success: false,
      error: 'Storage clearing is only available in development/test mode',
    });
    return;
  }

  try {
    await browserManager.clearStorage();
    res.status(200).json({
      success: true,
      message: 'Browser storage cleared successfully',
      timestamp: new Date().toISOString(),
    });
    return;
  } catch (error) {
    console.error('Error clearing storage:', error);
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    });
    return;
  }
});

/**
 * Reset browser context endpoint
 */
app.post('/api/context/reset', async (_req: Request, res: Response): Promise<void> => {
  const allowedEnvs = ['development', 'test'];
  if (!allowedEnvs.includes(NODE_ENV)) {
    res.status(403).json({
      success: false,
      error: 'Context reset is only available in development/test mode',
    });
    return;
  }

  try {
    await browserManager.resetContext();
    res.status(200).json({
      success: true,
      message: 'Browser context reset successfully',
      timestamp: new Date().toISOString(),
    });
    return;
  } catch (error) {
    console.error('Error resetting context:', error);
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    });
    return;
  }
});

/**
 * Root endpoint
 */
app.get('/', (_req: Request, res: Response) => {
  res.status(200).json({
    name: 'Purefoy Browser Automation Service',
    version: '0.1.0',
    description: 'Playwright-based browser automation for UI testing and screenshot capture',
    endpoints: {
      health: 'GET /health',
      navigate: 'POST /api/navigate',
      query: 'GET /api/element/exists',
      screenshot: 'POST /api/screenshot',
      sessions: 'GET /api/screenshot/sessions',
      close: 'POST /api/close',
    },
  });
});

/**
 * 404 handler
 */
app.use((_req: Request, res: Response) => {
  res.status(404).json({
    error: 'Not Found',
    message: 'The requested endpoint does not exist',
  });
});

/**
 * Start server
 */
app.listen(PORT, () => {
  console.log('Browser Automation Service');
  console.log(`  Environment:     ${NODE_ENV}`);
  console.log(`  Port:            ${PORT}`);
  console.log(`  Browser App:     ${BROWSER_APP_URL}`);
  console.log(`  Headless Mode:   ${HEADLESS}`);
  console.log(`  Server ready at: http://localhost:${PORT}`);
});

// Graceful shutdown
process.on('SIGTERM', async () => {
  console.log('SIGTERM received, shutting down gracefully...');
  await browserManager.close();
  process.exit(0);
});

process.on('SIGINT', async () => {
  console.log('\nSIGINT received, shutting down gracefully...');
  await browserManager.close();
  process.exit(0);
});
