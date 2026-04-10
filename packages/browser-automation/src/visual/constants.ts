export const VISUAL_THRESHOLDS = {
  PIXEL_PERFECT: 0,
  STRICT: 0.01,
  STANDARD: 0.1,
  LENIENT: 0.25,
  PERMISSIVE: 0.5,
} as const;

export type VisualThreshold = typeof VISUAL_THRESHOLDS[keyof typeof VISUAL_THRESHOLDS];

export const DEFAULT_DIFF_COLOR: [number, number, number] = [255, 0, 0];

export const DIFF_COLORS = {
  RED: [255, 0, 0] as [number, number, number],
  MAGENTA: [255, 0, 255] as [number, number, number],
  CYAN: [0, 255, 255] as [number, number, number],
  YELLOW: [255, 255, 0] as [number, number, number],
} as const;

export const DEFAULT_ALPHA = 0.1;

export const PLATFORM_EXTENSIONS = {
  DARWIN: '.darwin.png',
  LINUX: '.linux.png',
  WIN32: '.win32.png',
  GENERIC: '.png',
} as const;

export const BASELINE_CONFIG = {
  INDEX_FILE: 'index.json',
  DIFFS_DIR: 'diffs',
  MAX_DIFF_AGE_DAYS: 7,
  README_FILE: 'README.md',
  GITIGNORE_FILE: '.gitignore',
} as const;

export const IMAGE_FORMATS = {
  PNG: 'png',
  JPEG: 'jpeg',
} as const;

export const JPEG_QUALITY = {
  LOW: 60,
  MEDIUM: 80,
  HIGH: 95,
  MAX: 100,
} as const;

export const VALIDATION = {
  MIN_THRESHOLD: 0,
  MAX_THRESHOLD: 1,
  MIN_JPEG_QUALITY: 0,
  MAX_JPEG_QUALITY: 100,
  MIN_COLOR_VALUE: 0,
  MAX_COLOR_VALUE: 255,
  COLOR_ARRAY_LENGTH: 3,
} as const;
