import { compareScreenshots, ComparisonOptions } from '../../visual/comparison-engine.js';
import { BaselineManager, getBaselineManager } from '../../visual/baseline-manager.js';

export class VisualAssertions {
  private baselineManager: BaselineManager;

  constructor(private testSuite: string, private visualReporter?: any) {
    this.baselineManager = getBaselineManager();
  }

  async matchesBaseline(
    screenshotPath: string,
    name: string,
    options: ComparisonOptions & {
      updateBaseline?: boolean;
      createBaseline?: boolean;
    } = {}
  ): Promise<void> {
    const baselinePath = this.baselineManager.getBaselinePath(this.testSuite, name);
    const hasBaseline = this.baselineManager.hasBaseline(this.testSuite, name);

    if (!hasBaseline) {
      if (options.createBaseline !== false) {
        await this.baselineManager.saveBaseline(this.testSuite, name, screenshotPath);
        console.log(`Created new baseline: ${name}`);
        return;
      } else {
        throw new Error(
          `No baseline exists for "${name}". Run with createBaseline: true to create it.`
        );
      }
    }

    if (options.updateBaseline === true) {
      await this.baselineManager.saveBaseline(this.testSuite, name, screenshotPath);
      console.log(`Updated baseline: ${name}`);
      return;
    }

    const diffPath = this.baselineManager.getDiffPath(this.testSuite, name);

    const result = await compareScreenshots(baselinePath, screenshotPath, diffPath, options);

    if (this.visualReporter) {
      this.visualReporter.addVisualComparison(name, this.testSuite, result);
    }

    if (!result.matches) {
      const message =
        `Visual regression detected in "${name}":\n` +
        `  - Different pixels: ${result.diffPixelCount.toLocaleString()}\n` +
        `  - Difference: ${result.diffPercentage.toFixed(4)}%\n` +
        `  - Baseline: ${result.baselinePath}\n` +
        `  - Current: ${result.currentPath}\n` +
        `  - Diff: ${result.diffPath}\n\n` +
        `To update baseline:\n` +
        `  pnpm test:visual:update -- "${this.testSuite}" "${name}"`;

      throw new Error(message);
    }

    console.log(`Visual match: ${name} (0 pixel diff)`);
  }

  async hasChangedFromBaseline(
    screenshotPath: string,
    name: string,
    options: ComparisonOptions = {}
  ): Promise<void> {
    const baselinePath = this.baselineManager.getBaselinePath(this.testSuite, name);

    if (!this.baselineManager.hasBaseline(this.testSuite, name)) {
      throw new Error(`No baseline exists for "${name}"`);
    }

    const result = await compareScreenshots(baselinePath, screenshotPath, undefined, options);

    if (result.matches) {
      throw new Error(
        `Expected visual changes in "${name}" but screenshot matches baseline exactly`
      );
    }

    console.log(`Visual change detected as expected: ${name} (${result.diffPixelCount} pixels changed)`);
  }

  async diffWithinThreshold(
    screenshotPath: string,
    name: string,
    maxDiffPercentage: number,
    options: ComparisonOptions = {}
  ): Promise<void> {
    const baselinePath = this.baselineManager.getBaselinePath(this.testSuite, name);

    if (!this.baselineManager.hasBaseline(this.testSuite, name)) {
      throw new Error(`No baseline exists for "${name}"`);
    }

    const diffPath = this.baselineManager.getDiffPath(this.testSuite, name);
    const result = await compareScreenshots(baselinePath, screenshotPath, diffPath, options);

    if (this.visualReporter) {
      this.visualReporter.addVisualComparison(name, this.testSuite, result);
    }

    if (result.diffPercentage > maxDiffPercentage) {
      throw new Error(
        `Visual diff exceeds threshold for "${name}":\n` +
        `  - Actual: ${result.diffPercentage.toFixed(4)}%\n` +
        `  - Threshold: ${maxDiffPercentage.toFixed(4)}%\n` +
        `  - Different pixels: ${result.diffPixelCount.toLocaleString()}`
      );
    }

    console.log(`Visual diff within threshold: ${name} (${result.diffPercentage.toFixed(4)}% <= ${maxDiffPercentage}%)`);
  }

  async saveBaseline(screenshotPath: string, name: string): Promise<void> {
    await this.baselineManager.saveBaseline(this.testSuite, name, screenshotPath);
    console.log(`Saved baseline: ${name}`);
  }

  hasBaseline(name: string): boolean {
    return this.baselineManager.hasBaseline(this.testSuite, name);
  }
}

export function createVisualAssertions(
  testSuite: string,
  visualReporter?: any
): VisualAssertions {
  return new VisualAssertions(testSuite, visualReporter);
}
