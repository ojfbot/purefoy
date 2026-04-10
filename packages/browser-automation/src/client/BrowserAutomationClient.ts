/**
 * Type-safe Browser Automation API Client
 */

import axios, { AxiosInstance, AxiosError } from 'axios';
import {
  ClientConfig,
  NavigateOptions,
  NavigateResult,
  ClickOptions,
  TypeOptions,
  WaitOptions,
  ScreenshotOptions,
  ScreenshotResult,
  ElementQueryResult,
  AttributeResult,
  HealthResponse,
} from './types.js';
import { NetworkError, APIError, ElementNotFoundError, TimeoutError, ScreenshotError } from './errors.js';

const DEFAULT_TIMEOUT = 30000;
const CLOSE_MAX_RETRIES = 3;
const CLOSE_BASE_DELAY = 500;

export class BrowserAutomationClient {
  private axios: AxiosInstance;
  private config: ClientConfig;

  constructor(config: ClientConfig | string) {
    if (typeof config === 'string') {
      this.config = { baseUrl: config };
    } else {
      this.config = config;
    }
    this.axios = axios.create({
      baseURL: this.config.baseUrl,
      timeout: this.config.timeout || DEFAULT_TIMEOUT,
      headers: { 'Content-Type': 'application/json', ...this.config.headers },
    });
  }

  async health(): Promise<HealthResponse> {
    try {
      const response = await this.axios.get<HealthResponse>('/health');
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async navigate(url: string, options: NavigateOptions = {}): Promise<NavigateResult> {
    try {
      const response = await this.axios.post<NavigateResult>('/api/navigate', { url, ...options });
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async currentUrl(): Promise<string> {
    try {
      const health = await this.health();
      return health.browser.currentUrl || '';
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async elementExists(selector: string): Promise<boolean> {
    try {
      const response = await this.axios.get<ElementQueryResult>('/api/element/exists', {
        params: { selector },
      });
      return response.data.exists;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async elementVisible(selector: string): Promise<boolean> {
    try {
      const response = await this.axios.get<ElementQueryResult>('/api/element/exists', {
        params: { selector },
      });
      return response.data.visible || false;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async elementText(selector: string): Promise<string> {
    try {
      const response = await this.axios.get<ElementQueryResult>('/api/element/text', {
        params: { selector },
      });
      if (!response.data.success) throw new ElementNotFoundError(selector);
      return response.data.text || '';
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async elementAttribute(selector: string, attribute: string): Promise<string | null> {
    try {
      const response = await this.axios.get<AttributeResult>('/api/element/attribute', {
        params: { selector, attribute },
      });
      return response.data.value || null;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async pageTitle(): Promise<string> {
    try {
      const response = await this.axios.get<{ success: boolean; title: string }>('/api/page/title');
      return response.data.title || '';
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async elementHasFocus(selector: string): Promise<boolean> {
    try {
      const response = await this.axios.get<{ success: boolean; hasFocus: boolean }>(
        '/api/element/has-focus',
        { params: { selector } }
      );
      return response.data.hasFocus;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async elementCount(selector: string): Promise<number> {
    try {
      const response = await this.axios.get<ElementQueryResult>('/api/element/exists', {
        params: { selector },
      });
      return response.data.count || 0;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async click(selector: string, options: ClickOptions = {}): Promise<void> {
    try {
      await this.axios.post('/api/interact/click', { selector, ...options });
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async type(selector: string, text: string, options: TypeOptions = {}): Promise<void> {
    try {
      await this.axios.post('/api/interact/type', { selector, text, ...options });
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async fill(selector: string, text: string): Promise<void> {
    try {
      await this.axios.post('/api/interact/fill', { selector, text });
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async hover(selector: string): Promise<void> {
    try {
      await this.axios.post('/api/interact/hover', { selector });
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async press(key: string): Promise<void> {
    try {
      await this.axios.post('/api/interact/press', { key });
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async waitForSelector(selector: string, options: WaitOptions = {}): Promise<void> {
    try {
      await this.axios.post('/api/wait/element', { selector, ...options });
    } catch (error) {
      if (axios.isAxiosError(error) && error.code === 'ECONNABORTED') {
        throw new TimeoutError(`waitForSelector(${selector})`, options.timeout || DEFAULT_TIMEOUT);
      }
      throw this.handleError(error);
    }
  }

  async screenshot(options: ScreenshotOptions): Promise<ScreenshotResult> {
    try {
      const response = await this.axios.post<ScreenshotResult>('/api/screenshot', options);
      if (!response.data.success) throw new ScreenshotError('Screenshot capture failed');
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async close(): Promise<void> {
    for (let attempt = 0; attempt <= CLOSE_MAX_RETRIES; attempt++) {
      try {
        await this.axios.post('/api/close');
        return;
      } catch (error) {
        if (attempt === CLOSE_MAX_RETRIES) {
          console.warn(`Failed to close browser after ${CLOSE_MAX_RETRIES + 1} attempts`);
          return;
        }
        const delay = CLOSE_BASE_DELAY * Math.pow(2, attempt);
        await new Promise((resolve) => setTimeout(resolve, delay));
      }
    }
  }

  async clearStorage(): Promise<void> {
    try {
      await this.axios.post('/api/storage/clear');
    } catch (error) {
      throw this.handleError(error);
    }
  }

  async resetContext(): Promise<void> {
    try {
      await this.axios.post('/api/context/reset');
    } catch (error) {
      throw this.handleError(error);
    }
  }

  private handleError(error: unknown): Error {
    if (axios.isAxiosError(error)) {
      const axiosError = error as AxiosError;
      if (!axiosError.response) {
        return new NetworkError(axiosError.message || 'Network error occurred', axiosError);
      }
      const statusCode = axiosError.response.status;
      const data: any = axiosError.response.data;
      return new APIError(data?.error || axiosError.message, statusCode, data);
    }
    if (error instanceof Error) return error;
    return new Error(String(error));
  }
}
