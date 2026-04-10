import { SuiteResult } from '../types.js';

export interface Reporter {
  onSuiteStart(suiteName: string): void;
  onSuiteEnd(result: SuiteResult): void;
  onRunComplete(
    results: SuiteResult[],
    summary: {
      totalSuites: number;
      totalTests: number;
      passed: number;
      failed: number;
      skipped: number;
    }
  ): void;
}
