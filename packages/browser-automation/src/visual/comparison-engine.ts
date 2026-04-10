import fs from 'fs';
import path from 'path';
import { PNG } from 'pngjs';
import pixelmatch from 'pixelmatch';
import {
  VISUAL_THRESHOLDS,
  DEFAULT_DIFF_COLOR,
  DEFAULT_ALPHA,
  VALIDATION,
} from './constants.js';

export interface ComparisonOptions {
  threshold?: number;
  includeAA?: boolean;
  diffColor?: [number, number, number];
  alpha?: number;
}

export interface ComparisonResult {
  matches: boolean;
  diffPixelCount: number;
  diffPercentage: number;
  totalPixels: number;
  baselinePath: string;
  currentPath: string;
  diffPath?: string;
  timestamp: string;
  dimensions: {
    width: number;
    height: number;
  };
}

export interface BatchComparisonResult {
  successes: Map<string, ComparisonResult>;
  failures: Map<string, Error>;
}

export class ComparisonEngine {
  private defaultOptions: Required<ComparisonOptions> = {
    threshold: VISUAL_THRESHOLDS.STANDARD,
    includeAA: false,
    diffColor: DEFAULT_DIFF_COLOR,
    alpha: DEFAULT_ALPHA,
  };

  private validateOptions(options: ComparisonOptions): void {
    if (options.threshold !== undefined) {
      if (options.threshold < VALIDATION.MIN_THRESHOLD || options.threshold > VALIDATION.MAX_THRESHOLD) {
        throw new Error(`Threshold must be between ${VALIDATION.MIN_THRESHOLD} and ${VALIDATION.MAX_THRESHOLD}, got: ${options.threshold}`);
      }
    }

    if (options.alpha !== undefined) {
      if (options.alpha < VALIDATION.MIN_THRESHOLD || options.alpha > VALIDATION.MAX_THRESHOLD) {
        throw new Error(`Alpha must be between ${VALIDATION.MIN_THRESHOLD} and ${VALIDATION.MAX_THRESHOLD}, got: ${options.alpha}`);
      }
    }

    if (options.diffColor) {
      if (options.diffColor.length !== VALIDATION.COLOR_ARRAY_LENGTH) {
        throw new Error(`diffColor must be [R, G, B], got array of length: ${options.diffColor.length}`);
      }
      options.diffColor.forEach((value, index) => {
        if (value < VALIDATION.MIN_COLOR_VALUE || value > VALIDATION.MAX_COLOR_VALUE) {
          throw new Error(`diffColor[${index}] must be between ${VALIDATION.MIN_COLOR_VALUE} and ${VALIDATION.MAX_COLOR_VALUE}, got: ${value}`);
        }
      });
    }
  }

  async compare(
    baselinePath: string,
    currentPath: string,
    diffOutputPath?: string,
    options: ComparisonOptions = {}
  ): Promise<ComparisonResult> {
    this.validateOptions(options);

    if (!fs.existsSync(baselinePath)) {
      throw new Error(`Baseline screenshot not found: ${baselinePath}`);
    }
    if (!fs.existsSync(currentPath)) {
      throw new Error(`Current screenshot not found: ${currentPath}`);
    }

    const opts = { ...this.defaultOptions, ...options };

    const baseline = PNG.sync.read(fs.readFileSync(baselinePath));
    const current = PNG.sync.read(fs.readFileSync(currentPath));

    if (baseline.width !== current.width || baseline.height !== current.height) {
      throw new Error(
        `Screenshot dimensions don't match. Baseline: ${baseline.width}x${baseline.height}, Current: ${current.width}x${current.height}`
      );
    }

    const { width, height } = baseline;
    const totalPixels = width * height;

    const diff = new PNG({ width, height });

    const diffPixelCount = pixelmatch(
      baseline.data,
      current.data,
      diff.data,
      width,
      height,
      {
        threshold: opts.threshold,
        includeAA: opts.includeAA,
        diffColor: opts.diffColor,
        alpha: opts.alpha,
      }
    );

    const diffPercentage = (diffPixelCount / totalPixels) * 100;
    const matches = diffPixelCount === 0;

    let diffPath: string | undefined;
    if (diffOutputPath && diffPixelCount > 0) {
      const diffDir = path.dirname(diffOutputPath);
      if (!fs.existsSync(diffDir)) {
        fs.mkdirSync(diffDir, { recursive: true });
      }
      fs.writeFileSync(diffOutputPath, PNG.sync.write(diff));
      diffPath = diffOutputPath;
      console.log(`Diff image saved: ${diffOutputPath}`);
    }

    return {
      matches,
      diffPixelCount,
      diffPercentage,
      totalPixels,
      baselinePath,
      currentPath,
      diffPath,
      timestamp: new Date().toISOString(),
      dimensions: { width, height },
    };
  }

  async compareMultiple(
    comparisons: Array<{
      baselinePath: string;
      currentPath: string;
      diffOutputPath?: string;
      name?: string;
    }>,
    options: ComparisonOptions = {}
  ): Promise<BatchComparisonResult> {
    const successes = new Map<string, ComparisonResult>();
    const failures = new Map<string, Error>();

    for (const { baselinePath, currentPath, diffOutputPath, name } of comparisons) {
      const key = name || path.basename(currentPath);
      try {
        const result = await this.compare(baselinePath, currentPath, diffOutputPath, options);
        successes.set(key, result);
      } catch (error) {
        const err = error instanceof Error ? error : new Error(String(error));
        failures.set(key, err);
        console.error(`Comparison failed for ${key}:`, err.message);
      }
    }

    return { successes, failures };
  }

  generateSummary(results: Map<string, ComparisonResult>): {
    totalComparisons: number;
    passed: number;
    failed: number;
    totalDiffPixels: number;
    avgDiffPercentage: number;
  } {
    let totalDiffPixels = 0;
    let totalDiffPercentage = 0;
    let passed = 0;
    let failed = 0;

    results.forEach((result) => {
      totalDiffPixels += result.diffPixelCount;
      totalDiffPercentage += result.diffPercentage;
      if (result.matches) { passed++; } else { failed++; }
    });

    return {
      totalComparisons: results.size,
      passed,
      failed,
      totalDiffPixels,
      avgDiffPercentage: results.size > 0 ? totalDiffPercentage / results.size : 0,
    };
  }
}

export function createComparisonEngine(): ComparisonEngine {
  return new ComparisonEngine();
}

export async function compareScreenshots(
  baselinePath: string,
  currentPath: string,
  diffOutputPath?: string,
  options?: ComparisonOptions
): Promise<ComparisonResult> {
  const engine = new ComparisonEngine();
  return engine.compare(baselinePath, currentPath, diffOutputPath, options);
}
