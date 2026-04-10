import { TestFunction, TestContext, TestResult, TestStatus, AssertionAPI } from './types.js';

export class TestCase {
  private name: string;
  private fn: TestFunction;
  private timeoutMs: number;
  private shouldSkip: boolean = false;
  private assertionAPI: AssertionAPI;

  constructor(name: string, fn: TestFunction, assertionAPI: AssertionAPI, timeout: number = 30000) {
    this.name = name;
    this.fn = fn;
    this.assertionAPI = assertionAPI;
    this.timeoutMs = timeout;
  }

  async run(): Promise<TestResult> {
    const startTime = new Date();
    const result: TestResult = { name: this.name, status: TestStatus.PENDING, duration: 0, startTime };

    if (this.shouldSkip) {
      result.status = TestStatus.SKIPPED;
      result.endTime = new Date();
      result.duration = result.endTime.getTime() - startTime.getTime();
      return result;
    }

    result.status = TestStatus.RUNNING;
    try {
      const context: TestContext = {
        assert: this.assertionAPI,
        skip: () => { this.shouldSkip = true; throw new Error('Test skipped'); },
        timeout: (ms: number) => { this.timeoutMs = ms; },
      };
      await this.runWithTimeout(this.fn(context), this.timeoutMs);
      result.status = TestStatus.PASSED;
    } catch (error) {
      result.status = this.shouldSkip ? TestStatus.SKIPPED : TestStatus.FAILED;
      if (!this.shouldSkip) {
        result.error = error instanceof Error ? error : new Error(String(error));
      }
    } finally {
      const endTime = new Date();
      result.endTime = endTime;
      result.duration = endTime.getTime() - startTime.getTime();
    }
    return result;
  }

  private async runWithTimeout<T>(promise: Promise<T> | T, timeoutMs: number): Promise<T> {
    if (!(promise instanceof Promise)) return promise;
    return Promise.race([
      promise,
      new Promise<T>((_, reject) =>
        setTimeout(() => reject(new Error(`Test timeout after ${timeoutMs}ms`)), timeoutMs)
      ),
    ]);
  }

  getName(): string { return this.name; }
}
