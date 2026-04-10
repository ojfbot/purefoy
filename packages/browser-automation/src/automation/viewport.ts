/**
 * Viewport Management for Browser Automation
 */

export interface ViewportSize {
  width: number;
  height: number;
  deviceScaleFactor?: number;
  isMobile?: boolean;
  hasTouch?: boolean;
}

export type ViewportPreset = 'desktop' | 'tablet' | 'mobile' | 'mobile-landscape';

export const VIEWPORT_PRESETS: Record<ViewportPreset, ViewportSize> = {
  desktop: {
    width: 1920,
    height: 1080,
    deviceScaleFactor: 1,
    isMobile: false,
    hasTouch: false,
  },
  tablet: {
    width: 768,
    height: 1024,
    deviceScaleFactor: 2,
    isMobile: true,
    hasTouch: true,
  },
  mobile: {
    width: 375,
    height: 667,
    deviceScaleFactor: 2,
    isMobile: true,
    hasTouch: true,
  },
  'mobile-landscape': {
    width: 667,
    height: 375,
    deviceScaleFactor: 2,
    isMobile: true,
    hasTouch: true,
  },
};

export function getViewport(preset?: ViewportPreset | ViewportSize): ViewportSize {
  if (!preset) return VIEWPORT_PRESETS.desktop;
  if (typeof preset === 'string') return VIEWPORT_PRESETS[preset] || VIEWPORT_PRESETS.desktop;
  return preset;
}

export function getViewportSuffix(preset?: ViewportPreset | ViewportSize): string {
  if (!preset) return '';
  if (typeof preset === 'string') return `-${preset}`;
  return `-${preset.width}x${preset.height}`;
}
