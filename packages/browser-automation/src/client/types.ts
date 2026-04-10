/**
 * Type definitions for the Browser Automation API client
 */

export interface NavigateOptions {
  waitFor?: 'load' | 'domcontentloaded' | 'networkidle';
  timeout?: number;
}

export interface NavigateResult {
  success: boolean;
  currentUrl: string;
  title: string;
  timestamp: string;
}

export interface ClickOptions {
  button?: 'left' | 'right' | 'middle';
  clickCount?: number;
  delay?: number;
  timeout?: number;
}

export interface TypeOptions {
  delay?: number;
  timeout?: number;
}

export interface WaitOptions {
  state?: 'attached' | 'detached' | 'visible' | 'hidden';
  timeout?: number;
}

export type ViewportPreset = 'desktop' | 'tablet' | 'mobile';

export interface ScreenshotOptions {
  name: string;
  selector?: string;
  fullPage?: boolean;
  viewport?: ViewportPreset | { width: number; height: number };
  sessionDir?: string;
  format?: 'png' | 'jpeg';
  quality?: number;
}

export interface ScreenshotResult {
  success: boolean;
  filename: string;
  path: string;
  timestamp: string;
  viewport?: { width: number; height: number };
}

export interface ElementQueryResult {
  success: boolean;
  exists: boolean;
  visible?: boolean;
  count?: number;
  text?: string;
}

export interface AttributeResult {
  success: boolean;
  value: string | null;
}

export interface ClientConfig {
  baseUrl: string;
  timeout?: number;
  retries?: number;
  headers?: Record<string, string>;
}

export interface HealthResponse {
  status: string;
  service?: string;
  version?: string;
  environment?: string;
  browser: {
    running: boolean;
    currentUrl: string | null;
    connected: boolean;
    session: string | null;
  };
  config?: {
    browserAppUrl: string;
    headless: boolean;
    port: string;
  };
  timestamp: string;
}
