import { TestSuite } from './TestSuite.js';
import { RunnerConfig, SuiteResult } from './types.js';
import { ConsoleReporter } from './reporters/ConsoleReporter.js';
import { Reporter } from './reporters/Reporter.js';

export class TestRunner {
  private config: RunnerConfig;
  private reporters: Reporter[] = [];

  constructor(config: RunnerConfig = {}) {
    this.config = { reporters: ['console'], bail: false, verbose: false, ...config };
    this.initializeReporters();
  }

  private initializeReporters(): void {
    const reporterTypes = this.config.reporters || ['console'];
    for (const type of reporterTypes) {
      if (type === 'console') {
        this.reporters.push(new ConsoleReporter(this.config.verbose || false));
      } else if (typeof type === 'object' && type !== null) {
        this.reporters.push(type as Reporter);
      }
    }
  }

  async run(suite: TestSuite): Promise<SuiteResult> {
    try {
      for (const reporter of this.reporters) reporter.onSuiteStart(suite.getName());
      const result = await suite.run(this.config.filter);
      for (const reporter of this.reporters) reporter.onSuiteEnd(result);

      // Call onRunComplete
      const summary = {
        totalSuites: 1,
        totalTests: result.summary.total,
        passed: result.summary.passed,
        failed: result.summary.failed,
        skipped: result.summary.skipped,
      };
      for (const reporter of this.reporters) reporter.onRunComplete([result], summary);

      return result;
    } catch (error) {
      const errorResult: SuiteResult = {
        name: suite.getName(), tests: [], duration: 0,
        summary: { total: 0, passed: 0, failed: 1, skipped: 0 },
        startTime: new Date(), endTime: new Date(),
      };
      for (const reporter of this.reporters) reporter.onSuiteEnd(errorResult);
      throw error;
    }
  }

  static getExitCode(results: { summary: { failed: number } }): number {
    return results.summary.failed > 0 ? 1 : 0;
  }
}
