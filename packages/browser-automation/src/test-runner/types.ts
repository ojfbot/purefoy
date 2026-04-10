/**
 * Core types for the test framework
 */

export enum TestStatus {
  PENDING = 'pending',
  RUNNING = 'running',
  PASSED = 'passed',
  FAILED = 'failed',
  SKIPPED = 'skipped',
}

export interface TestResult {
  name: string;
  status: TestStatus;
  duration: number;
  error?: Error;
  startTime: Date;
  endTime?: Date;
}

export interface SuiteResult {
  name: string;
  tests: TestResult[];
  duration: number;
  summary: { total: number; passed: number; failed: number; skipped: number };
  startTime: Date;
  endTime?: Date;
}

export type TestFunction = (context: TestContext) => Promise<void> | void;
export type HookFunction = () => Promise<void> | void;

export interface TestContext {
  assert: AssertionAPI;
  skip: () => void;
  timeout: (ms: number) => void;
}

export interface AssertionAPI {
  elementExists(selector: string, message?: string): Promise<void>;
  elementVisible(selector: string, message?: string): Promise<void>;
  elementHidden(selector: string, message?: string): Promise<void>;
  elementCount(selector: string, count: number, message?: string): Promise<void>;
  textContains(selector: string, text: string, message?: string): Promise<void>;
  attributeEquals(selector: string, attr: string, value: string, message?: string): Promise<void>;
  screenshotCaptured(result: any, message?: string): void;
  urlContains(fragment: string, message?: string): Promise<void>;
  titleContains(text: string, message?: string): Promise<void>;
  elementHasFocus(selector: string, message?: string): Promise<void>;
}

export interface SuiteOptions {
  baseUrl?: string;
  screenshotDir?: string;
  timeout?: number;
  retries?: number;
  parallel?: boolean;
}

export interface RunnerConfig {
  reporters?: ('console' | 'json' | 'markdown' | any)[];
  outputDir?: string;
  bail?: boolean;
  verbose?: boolean;
  filter?: string;
  stopOnFailure?: boolean;
}
