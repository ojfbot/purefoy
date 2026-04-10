import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

function findProjectRoot(): string {
  if (process.env.BASELINE_ROOT) {
    return path.resolve(process.env.BASELINE_ROOT);
  }

  let currentDir = __dirname;
  const rootMarkers = ['pnpm-workspace.yaml', 'lerna.json', '.git'];

  while (currentDir !== path.parse(currentDir).root) {
    for (const marker of rootMarkers) {
      if (fs.existsSync(path.join(currentDir, marker))) {
        return currentDir;
      }
    }

    try {
      const packageJsonPath = path.join(currentDir, 'package.json');
      if (fs.existsSync(packageJsonPath)) {
        const pkg = JSON.parse(fs.readFileSync(packageJsonPath, 'utf-8'));
        if (pkg.workspaces || (pkg.private === true && fs.existsSync(path.join(currentDir, 'packages')))) {
          return currentDir;
        }
        if (pkg.name === '@purefoy/browser-automation') {
          return path.resolve(currentDir, '../..');
        }
      }
    } catch (_) {}

    currentDir = path.dirname(currentDir);
  }

  return path.resolve(__dirname, '../../..');
}

const PROJECT_ROOT = findProjectRoot();
const BASELINES_DIR = path.join(PROJECT_ROOT, 'packages/browser-automation/test-baselines');

export interface BaselineMetadata {
  id: string;
  testName: string;
  name: string;
  viewport?: string;
  createdAt: string;
  updatedAt: string;
  gitCommit?: string;
  dimensions: { width: number; height: number };
  fileSize: number;
  platform?: string;
}

export interface BaselineIndex {
  version: string;
  updatedAt: string;
  baselines: Record<string, BaselineMetadata>;
}

export class BaselineManager {
  private baselinesDir: string;
  private indexPath: string;
  private initPromise: Promise<void> | null = null;

  constructor(baselinesDir: string = BASELINES_DIR) {
    this.baselinesDir = baselinesDir;
    this.indexPath = path.join(baselinesDir, 'index.json');
  }

  async initialize(): Promise<void> {
    if (this.initPromise) return this.initPromise;
    this.initPromise = this._initialize();
    return this.initPromise;
  }

  private async _initialize(): Promise<void> {
    if (!fs.existsSync(this.baselinesDir)) {
      fs.mkdirSync(this.baselinesDir, { recursive: true });
    }

    if (!fs.existsSync(this.indexPath)) {
      const index: BaselineIndex = {
        version: '1.0.0',
        updatedAt: new Date().toISOString(),
        baselines: {},
      };
      this.saveIndex(index);
    }

    const gitignorePath = path.join(this.baselinesDir, '.gitignore');
    if (!fs.existsSync(gitignorePath)) {
      fs.writeFileSync(
        gitignorePath,
        '# Baseline screenshots are tracked in git\n# Only ignore diffs and temp files\n*.diff.png\n*.tmp.png\n.DS_Store\n'
      );
    }
  }

  getBaselinePath(testSuite: string, screenshotName: string, usePlatform = true): string {
    const suiteDir = path.join(this.baselinesDir, this.sanitizePath(testSuite));

    if (usePlatform) {
      const platformName = `${screenshotName}.${process.platform}.png`;
      const platformPath = path.join(suiteDir, platformName);
      if (fs.existsSync(platformPath)) {
        return platformPath;
      }
    }

    return path.join(suiteDir, `${screenshotName}.png`);
  }

  async saveBaseline(
    testSuite: string,
    screenshotName: string,
    sourcePath: string,
    metadata: Partial<BaselineMetadata> = {}
  ): Promise<string> {
    await this.initialize();

    const suiteDir = path.join(this.baselinesDir, this.sanitizePath(testSuite));
    if (!fs.existsSync(suiteDir)) {
      fs.mkdirSync(suiteDir, { recursive: true });
    }

    const baselinePath = path.join(suiteDir, `${screenshotName}.png`);
    fs.copyFileSync(sourcePath, baselinePath);

    const stats = fs.statSync(baselinePath);
    const PNG = await import('pngjs').then((m) => m.PNG);
    const imageData = PNG.sync.read(fs.readFileSync(baselinePath));

    const index = this.loadIndex();
    const id = `${testSuite}/${screenshotName}`;

    index.baselines[id] = {
      id,
      testName: testSuite,
      name: screenshotName,
      createdAt: index.baselines[id]?.createdAt || new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      dimensions: { width: imageData.width, height: imageData.height },
      fileSize: stats.size,
      platform: process.platform,
      ...metadata,
    };

    this.saveIndex(index);
    console.log(`Baseline saved: ${baselinePath}`);
    return baselinePath;
  }

  hasBaseline(testSuite: string, screenshotName: string): boolean {
    const baselinePath = this.getBaselinePath(testSuite, screenshotName);
    return fs.existsSync(baselinePath);
  }

  getBaselineMetadata(testSuite: string, screenshotName: string): BaselineMetadata | null {
    const index = this.loadIndex();
    const id = `${testSuite}/${screenshotName}`;
    return index.baselines[id] || null;
  }

  listBaselines(testSuite?: string): BaselineMetadata[] {
    const index = this.loadIndex();
    if (testSuite) {
      return Object.values(index.baselines).filter((b) => b.testName === testSuite);
    }
    return Object.values(index.baselines);
  }

  async deleteBaseline(testSuite: string, screenshotName: string): Promise<void> {
    const baselinePath = this.getBaselinePath(testSuite, screenshotName, false);
    if (fs.existsSync(baselinePath)) {
      fs.unlinkSync(baselinePath);
    }

    const index = this.loadIndex();
    const id = `${testSuite}/${screenshotName}`;
    delete index.baselines[id];
    this.saveIndex(index);
  }

  getDiffPath(testSuite: string, screenshotName: string): string {
    const suiteDir = path.join(this.baselinesDir, this.sanitizePath(testSuite), 'diffs');
    if (!fs.existsSync(suiteDir)) {
      fs.mkdirSync(suiteDir, { recursive: true });
    }
    return path.join(suiteDir, `${screenshotName}.diff.png`);
  }

  private loadIndex(): BaselineIndex {
    if (!fs.existsSync(this.indexPath)) {
      return { version: '1.0.0', updatedAt: new Date().toISOString(), baselines: {} };
    }
    return JSON.parse(fs.readFileSync(this.indexPath, 'utf-8'));
  }

  private saveIndex(index: BaselineIndex): void {
    index.updatedAt = new Date().toISOString();
    fs.writeFileSync(this.indexPath, JSON.stringify(index, null, 2));
  }

  private sanitizePath(name: string): string {
    return name.replace(/[^a-zA-Z0-9-_]/g, '-').toLowerCase();
  }
}

export function getBaselineManager(): BaselineManager {
  return new BaselineManager();
}
