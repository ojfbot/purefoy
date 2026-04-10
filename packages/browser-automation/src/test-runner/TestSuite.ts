import { TestCase } from './TestCase.js';
import { TestFunction, HookFunction, SuiteOptions, SuiteResult, TestStatus, AssertionAPI } from './types.js';
import { TEST_TIMEOUTS } from './constants.js';

export class TestSuite {
  private name: string;
  private tests: TestCase[] = [];
  private options: SuiteOptions;
  private beforeAllHooks: HookFunction[] = [];
  private afterAllHooks: HookFunction[] = [];
  private beforeEachHooks: HookFunction[] = [];
  private afterEachHooks: HookFunction[] = [];
  private assertionAPI: AssertionAPI;

  constructor(name: string, assertionAPI: AssertionAPI, options: SuiteOptions = {}) {
    this.name = name;
    this.assertionAPI = assertionAPI;
    this.options = { timeout: TEST_TIMEOUTS.DEFAULT, retries: 0, parallel: false, ...options };
  }

  test(name: string, fn: TestFunction): void {
    this.tests.push(new TestCase(name, fn, this.assertionAPI, this.options.timeout));
  }

  beforeAll(fn: HookFunction): void { this.beforeAllHooks.push(fn); }
  afterAll(fn: HookFunction): void { this.afterAllHooks.push(fn); }
  beforeEach(fn: HookFunction): void { this.beforeEachHooks.push(fn); }
  afterEach(fn: HookFunction): void { this.afterEachHooks.push(fn); }

  async run(filter?: string): Promise<SuiteResult> {
    const startTime = new Date();
    const result: SuiteResult = {
      name: this.name, tests: [], duration: 0,
      summary: { total: 0, passed: 0, failed: 0, skipped: 0 }, startTime,
    };

    try {
      await this.runHooks(this.beforeAllHooks);
      const testsToRun = filter ? this.tests.filter((t) => t.getName().includes(filter)) : this.tests;
      result.summary.total = testsToRun.length;

      for (const test of testsToRun) {
        await this.runHooks(this.beforeEachHooks);
        const testResult = await test.run();
        result.tests.push(testResult);
        await this.runHooks(this.afterEachHooks);
      }

      result.summary.passed = result.tests.filter((t) => t.status === TestStatus.PASSED).length;
      result.summary.failed = result.tests.filter((t) => t.status === TestStatus.FAILED).length;
      result.summary.skipped = result.tests.filter((t) => t.status === TestStatus.SKIPPED).length;
    } finally {
      await this.runHooks(this.afterAllHooks);
      const endTime = new Date();
      result.endTime = endTime;
      result.duration = endTime.getTime() - startTime.getTime();
    }
    return result;
  }

  private async runHooks(hooks: HookFunction[]): Promise<void> {
    for (const hook of hooks) await hook();
  }

  getName(): string { return this.name; }
}
