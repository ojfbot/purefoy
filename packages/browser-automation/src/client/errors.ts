/**
 * Custom error classes for Browser Automation Client
 */

export class BrowserAutomationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'BrowserAutomationError';
  }
}

export class NetworkError extends BrowserAutomationError {
  constructor(
    message: string,
    public readonly originalError?: Error
  ) {
    super(message);
    this.name = 'NetworkError';
  }
}

export class APIError extends BrowserAutomationError {
  constructor(
    message: string,
    public readonly statusCode: number,
    public readonly response?: any
  ) {
    super(message);
    this.name = 'APIError';
  }
}

export class ElementNotFoundError extends BrowserAutomationError {
  constructor(selector: string) {
    super(`Element not found: ${selector}`);
    this.name = 'ElementNotFoundError';
  }
}

export class TimeoutError extends BrowserAutomationError {
  constructor(operation: string, timeout: number) {
    super(`Operation "${operation}" timed out after ${timeout}ms`);
    this.name = 'TimeoutError';
  }
}

export class ScreenshotError extends BrowserAutomationError {
  constructor(message: string) {
    super(message);
    this.name = 'ScreenshotError';
  }
}
