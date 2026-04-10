import chalk from 'chalk';
import { Reporter } from './Reporter.js';
import { SuiteResult, TestStatus } from '../types.js';

export class ConsoleReporter implements Reporter {
  private verbose: boolean;

  constructor(verbose: boolean = false) {
    this.verbose = verbose;
  }

  onSuiteStart(suiteName: string): void {
    console.log();
    console.log(chalk.bold(`Running test suite: ${suiteName}`));
    console.log();
  }

  onSuiteEnd(result: SuiteResult): void {
    for (const test of result.tests) {
      const symbol = this.getSymbol(test.status);
      const color = this.getColor(test.status);
      const duration = this.formatDuration(test.duration);

      console.log(`  ${color(symbol)} ${test.name} ${chalk.gray(duration)}`);

      if (test.status === TestStatus.FAILED && test.error) {
        console.log();
        console.log(chalk.red('    Error: ' + test.error.message));
        if (this.verbose && test.error.stack) {
          console.log(chalk.gray(this.indent(test.error.stack, 4)));
        }
        console.log();
      }
    }

    console.log();
    this.printSummary(result);
  }

  onRunComplete(
    _results: SuiteResult[],
    summary: {
      totalSuites: number;
      totalTests: number;
      passed: number;
      failed: number;
      skipped: number;
    }
  ): void {
    console.log();
    console.log(chalk.bold('='.repeat(60)));
    console.log(chalk.bold('  Test Run Summary'));
    console.log(chalk.bold('='.repeat(60)));
    console.log();

    console.log(`  ${chalk.bold('Suites:')}  ${summary.totalSuites}`);
    console.log(`  ${chalk.bold('Tests:')}   ${summary.totalTests}`);
    console.log(`  ${chalk.green('Passed:')} ${summary.passed}`);

    if (summary.failed > 0) {
      console.log(`  ${chalk.red('Failed:')} ${summary.failed}`);
    }

    if (summary.skipped > 0) {
      console.log(`  ${chalk.yellow('Skipped:')} ${summary.skipped}`);
    }

    console.log();

    if (summary.failed === 0) {
      console.log(chalk.green.bold('  All tests passed!'));
    } else {
      console.log(chalk.red.bold(`  ${summary.failed} test(s) failed`));
    }

    console.log();
    console.log(chalk.bold('='.repeat(60)));
    console.log();
  }

  private printSummary(result: SuiteResult): void {
    const { summary } = result;
    const duration = this.formatDuration(result.duration);

    const parts = [];
    parts.push(chalk.green(`${summary.passed} passed`));
    if (summary.failed > 0) parts.push(chalk.red(`${summary.failed} failed`));
    if (summary.skipped > 0) parts.push(chalk.yellow(`${summary.skipped} skipped`));

    console.log(`  ${parts.join(', ')}`);
    console.log(`  ${chalk.gray(`Total time: ${duration}`)}`);
  }

  private getSymbol(status: TestStatus): string {
    switch (status) {
      case TestStatus.PASSED: return 'PASS';
      case TestStatus.FAILED: return 'FAIL';
      case TestStatus.SKIPPED: return 'SKIP';
      default: return '...';
    }
  }

  private getColor(status: TestStatus): (text: string) => string {
    switch (status) {
      case TestStatus.PASSED: return chalk.green;
      case TestStatus.FAILED: return chalk.red;
      case TestStatus.SKIPPED: return chalk.yellow;
      default: return chalk.gray;
    }
  }

  private formatDuration(ms: number): string {
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  }

  private indent(text: string, spaces: number): string {
    const indentation = ' '.repeat(spaces);
    return text.split('\n').map((line) => indentation + line).join('\n');
  }
}
