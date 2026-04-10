export {
  ComparisonEngine,
  ComparisonOptions,
  ComparisonResult,
  BatchComparisonResult,
  createComparisonEngine,
  compareScreenshots,
} from './comparison-engine.js';

export {
  BaselineManager,
  BaselineMetadata,
  BaselineIndex,
  getBaselineManager,
} from './baseline-manager.js';

export {
  VISUAL_THRESHOLDS,
  DIFF_COLORS,
  DEFAULT_DIFF_COLOR,
  DEFAULT_ALPHA,
  BASELINE_CONFIG,
  PLATFORM_EXTENSIONS,
  IMAGE_FORMATS,
  JPEG_QUALITY,
  VALIDATION,
  type VisualThreshold,
} from './constants.js';
