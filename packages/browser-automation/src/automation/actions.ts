/**
 * User Interaction Actions
 */

import { Page } from 'playwright';

export interface ClickOptions {
  timeout?: number;
  force?: boolean;
  position?: { x: number; y: number };
  button?: 'left' | 'right' | 'middle';
  clickCount?: number;
  delay?: number;
}

export interface TypeOptions {
  timeout?: number;
  delay?: number;
  clear?: boolean;
}

export interface HoverOptions {
  timeout?: number;
  force?: boolean;
  position?: { x: number; y: number };
}

export interface InteractionResult {
  success: boolean;
  elementFound: boolean;
  error?: string;
}

export async function clickElement(
  page: Page,
  selector: string,
  options: ClickOptions = {}
): Promise<InteractionResult> {
  try {
    const element = page.locator(selector).first();
    const exists = (await element.count()) > 0;
    if (!exists) {
      return { success: false, elementFound: false, error: `Element not found: ${selector}` };
    }
    await element.waitFor({ state: 'visible', timeout: options.timeout || 30000 });
    await element.click({
      force: options.force,
      position: options.position,
      button: options.button,
      clickCount: options.clickCount,
      delay: options.delay,
      timeout: options.timeout || 30000,
    });
    return { success: true, elementFound: true };
  } catch (error) {
    return {
      success: false,
      elementFound: true,
      error: error instanceof Error ? error.message : 'Click failed',
    };
  }
}

export async function typeIntoElement(
  page: Page,
  selector: string,
  text: string,
  options: TypeOptions = {}
): Promise<InteractionResult> {
  try {
    const element = page.locator(selector).first();
    const exists = (await element.count()) > 0;
    if (!exists) {
      return { success: false, elementFound: false, error: `Element not found: ${selector}` };
    }
    await element.waitFor({ state: 'visible', timeout: options.timeout || 30000 });
    if (options.clear) await element.clear();
    await element.pressSequentially(text, {
      delay: options.delay,
      timeout: options.timeout || 30000,
    });
    return { success: true, elementFound: true };
  } catch (error) {
    return {
      success: false,
      elementFound: true,
      error: error instanceof Error ? error.message : 'Type failed',
    };
  }
}

export async function hoverOverElement(
  page: Page,
  selector: string,
  options: HoverOptions = {}
): Promise<InteractionResult> {
  try {
    const element = page.locator(selector).first();
    const exists = (await element.count()) > 0;
    if (!exists) {
      return { success: false, elementFound: false, error: `Element not found: ${selector}` };
    }
    await element.waitFor({ state: 'visible', timeout: options.timeout || 30000 });
    await element.hover({
      force: options.force,
      position: options.position,
      timeout: options.timeout || 30000,
    });
    return { success: true, elementFound: true };
  } catch (error) {
    return {
      success: false,
      elementFound: true,
      error: error instanceof Error ? error.message : 'Hover failed',
    };
  }
}

export async function fillElement(
  page: Page,
  selector: string,
  text: string,
  options: { timeout?: number } = {}
): Promise<InteractionResult> {
  try {
    const element = page.locator(selector).first();
    const exists = (await element.count()) > 0;
    if (!exists) {
      return { success: false, elementFound: false, error: `Element not found: ${selector}` };
    }
    await element.fill(text, { timeout: options.timeout || 30000 });
    return { success: true, elementFound: true };
  } catch (error) {
    return {
      success: false,
      elementFound: true,
      error: error instanceof Error ? error.message : 'Fill failed',
    };
  }
}

export async function pressKey(
  page: Page,
  key: string,
  options: { delay?: number } = {}
): Promise<InteractionResult> {
  try {
    await page.keyboard.press(key, { delay: options.delay });
    return { success: true, elementFound: true };
  } catch (error) {
    return {
      success: false,
      elementFound: true,
      error: error instanceof Error ? error.message : 'Press key failed',
    };
  }
}

export async function selectOption(
  page: Page,
  selector: string,
  value: string | string[],
  options: { timeout?: number } = {}
): Promise<InteractionResult> {
  try {
    const element = page.locator(selector).first();
    const exists = (await element.count()) > 0;
    if (!exists) {
      return { success: false, elementFound: false, error: `Element not found: ${selector}` };
    }
    await element.selectOption(value, { timeout: options.timeout || 30000 });
    return { success: true, elementFound: true };
  } catch (error) {
    return {
      success: false,
      elementFound: true,
      error: error instanceof Error ? error.message : 'Select option failed',
    };
  }
}

export async function setChecked(
  page: Page,
  selector: string,
  checked: boolean,
  options: { timeout?: number; force?: boolean } = {}
): Promise<InteractionResult> {
  try {
    const element = page.locator(selector).first();
    const exists = (await element.count()) > 0;
    if (!exists) {
      return { success: false, elementFound: false, error: `Element not found: ${selector}` };
    }
    await element.setChecked(checked, {
      timeout: options.timeout || 30000,
      force: options.force,
    });
    return { success: true, elementFound: true };
  } catch (error) {
    return {
      success: false,
      elementFound: true,
      error: error instanceof Error ? error.message : 'Set checked failed',
    };
  }
}
