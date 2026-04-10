import { BrowserAutomationClient } from '../../client/BrowserAutomationClient.js';
import { ScreenshotResult } from '../../client/types.js';
import { AssertionAPI } from '../types.js';

export class AssertionError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'AssertionError';
  }
}

export class Assertions implements AssertionAPI {
  constructor(private client: BrowserAutomationClient) {}

  async elementExists(selector: string, message?: string): Promise<void> {
    const exists = await this.client.elementExists(selector);
    if (!exists) {
      throw new AssertionError(
        message || `Expected element "${selector}" to exist, but it was not found`
      );
    }
  }

  async elementVisible(selector: string, message?: string): Promise<void> {
    const visible = await this.client.elementVisible(selector);
    if (!visible) {
      throw new AssertionError(
        message || `Expected element "${selector}" to be visible, but it was hidden or not found`
      );
    }
  }

  async elementHidden(selector: string, message?: string): Promise<void> {
    const visible = await this.client.elementVisible(selector);
    if (visible) {
      throw new AssertionError(
        message || `Expected element "${selector}" to be hidden, but it was visible`
      );
    }
  }

  async elementCount(selector: string, count: number, message?: string): Promise<void> {
    const actual = await this.client.elementCount(selector);
    if (actual !== count) {
      throw new AssertionError(
        message || `Expected ${count} element(s) matching "${selector}", but found ${actual}`
      );
    }
  }

  async textContains(selector: string, text: string, message?: string): Promise<void> {
    const actualText = await this.client.elementText(selector);
    if (!actualText.includes(text)) {
      throw new AssertionError(
        message || `Expected element "${selector}" to contain text "${text}", but got "${actualText}"`
      );
    }
  }

  async attributeEquals(
    selector: string,
    attr: string,
    value: string,
    message?: string
  ): Promise<void> {
    const actualValue = await this.client.elementAttribute(selector, attr);
    if (actualValue !== value) {
      throw new AssertionError(
        message || `Expected element "${selector}" attribute "${attr}" to equal "${value}", but got "${actualValue}"`
      );
    }
  }

  screenshotCaptured(result: ScreenshotResult, message?: string): void {
    if (!result.success) {
      throw new AssertionError(message || 'Expected screenshot to be captured successfully');
    }
  }

  async urlContains(fragment: string, message?: string): Promise<void> {
    const currentUrl = await this.client.currentUrl();
    if (!currentUrl.includes(fragment)) {
      throw new AssertionError(
        message || `Expected URL to contain "${fragment}", but got "${currentUrl}"`
      );
    }
  }

  async titleContains(text: string, message?: string): Promise<void> {
    const title = await this.client.pageTitle();
    if (!title.includes(text)) {
      throw new AssertionError(
        message || `Expected page title to contain "${text}", but got "${title}"`
      );
    }
  }

  async elementHasFocus(selector: string, message?: string): Promise<void> {
    const hasFocus = await this.client.elementHasFocus(selector);
    if (!hasFocus) {
      throw new AssertionError(
        message || `Expected element "${selector}" to have focus, but document.activeElement does not match`
      );
    }
  }
}

export function createAssertions(client: BrowserAutomationClient): AssertionAPI {
  return new Assertions(client);
}
