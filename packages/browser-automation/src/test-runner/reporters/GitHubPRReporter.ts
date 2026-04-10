import fs from 'fs';
import path from 'path';
import { Reporter } from './Reporter.js';
import { TestResult, TestStatus, SuiteResult } from '../types.js';

export interface GitHubPRReporterOptions {
  outputPath: string;
  runNumber?: string;
  runId?: string;
  repository?: string;
}

interface VisualDiffInfo {
  testName: string;
  diffPath?: string;
  baselinePath?: string;
  currentPath?: string;
  differentPixels: string;
  differencePercent: string;
}

export class GitHubPRReporter implements Reporter {
  private options: GitHubPRReporterOptions;
  private results: TestResult[] = [];
  private visualDiffs: Map<string, VisualDiffInfo> = new Map();

  constructor(options: GitHubPRReporterOptions) {
    this.options = options;
  }

  onSuiteStart(_suiteName: string): void {}

  onSuiteEnd(result: SuiteResult): void {
    this.results.push(...result.tests);

    for (const testResult of result.tests) {
      if (testResult.error && testResult.error.message?.includes('Visual regression detected')) {
        this.extractVisualDiffInfo(testResult);
      }
    }
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
    const markdown = this.generateMarkdown(summary);

    const outputDir = path.dirname(this.options.outputPath);
    if (!fs.existsSync(outputDir)) {
      fs.mkdirSync(outputDir, { recursive: true });
    }

    fs.writeFileSync(this.options.outputPath, markdown);
    console.log(`GitHub PR comment saved to: ${this.options.outputPath}`);
  }

  private extractVisualDiffInfo(result: TestResult): void {
    const errorMsg = result.error?.message || '';

    const diffMatch = errorMsg.match(/- Diff: (.+\.diff\.png)/);
    const baselineMatch = errorMsg.match(/- Baseline: (.+\.png)/);
    const currentMatch = errorMsg.match(/- Current: (.+\.png)/);
    const diffPixelsMatch = errorMsg.match(/- Different pixels: ([\d,]+)/);
    const diffPercentMatch = errorMsg.match(/- Difference: ([\d.]+)%/);

    if (diffMatch) {
      this.visualDiffs.set(result.name, {
        testName: result.name,
        diffPath: diffMatch[1],
        baselinePath: baselineMatch?.[1],
        currentPath: currentMatch?.[1],
        differentPixels: diffPixelsMatch?.[1] || '0',
        differencePercent: diffPercentMatch?.[1] || '0',
      });
    }
  }

  private generateMarkdown(summary: {
    totalSuites: number;
    totalTests: number;
    passed: number;
    failed: number;
    skipped: number;
  }): string {
    const { passed, failed, skipped, totalTests } = summary;
    const hasFailures = failed > 0;

    let markdown = `## Browser Automation Test Results\n\n`;

    markdown += '### Summary\n\n';
    markdown += `| Metric | Count |\n`;
    markdown += `|--------|-------|\n`;
    markdown += `| Passed | ${passed} |\n`;
    markdown += `| Failed | ${failed} |\n`;
    markdown += `| Skipped | ${skipped} |\n`;
    markdown += `| Total | ${totalTests} |\n\n`;

    if (this.visualDiffs.size > 0) {
      markdown += `### Visual Regression Differences\n\n`;
      markdown += `Found ${this.visualDiffs.size} visual regression(s):\n\n`;

      for (const [testName, info] of this.visualDiffs) {
        markdown += `#### ${testName}\n\n`;
        markdown += `| Metric | Value |\n`;
        markdown += `|--------|-------|\n`;
        markdown += `| Different Pixels | ${info.differentPixels} |\n`;
        markdown += `| Difference | ${info.differencePercent}% |\n\n`;
      }

      markdown += '---\n\n';
    }

    if (failed > 0) {
      const failedTests = this.results.filter((r) => r.status === TestStatus.FAILED);
      markdown += '### Failed Tests\n\n';

      for (const test of failedTests) {
        markdown += `<details>\n`;
        markdown += `<summary><b>${test.name}</b> (${test.duration}ms)</summary>\n\n`;
        if (test.error) {
          markdown += `\`\`\`\n${test.error.message || 'Unknown error'}\n\`\`\`\n\n`;
        }
        markdown += `</details>\n\n`;
      }
    }

    if (this.options.runId && this.options.repository) {
      const baseUrl = `https://github.com/${this.options.repository}/actions/runs/${this.options.runId}`;
      markdown += `### Artifacts\n\n`;
      markdown += `Download artifacts from the [CI run](${baseUrl}).\n\n`;
    }

    if (hasFailures) {
      markdown += '### Updating Baselines\n\n';
      markdown += '```bash\n';
      markdown += 'UPDATE_BASELINES=true pnpm --filter @purefoy/browser-automation test:visual\n';
      markdown += 'git add packages/browser-automation/test-baselines/\n';
      markdown += 'git commit -m "chore: update visual regression baselines"\n';
      markdown += 'git push\n';
      markdown += '```\n\n';
    }

    return markdown;
  }
}
