/**
 * Skeldir Level 0 — Token registry (TypeScript mirror for audits & programmatic access)
 */

export const COLOR_TOKENS = [
  'bg.page',
  'bg.sidebar',
  'bg.header',
  'bg.card',
  'bg.muted',
  'text.primary',
  'text.secondary',
  'text.muted',
  'text.inverse',
  'border.default',
  'trust.deterministic',
  'trust.probabilistic',
  'trust.benchmark',
  'trust.prior',
  'trust.unavailable',
  'trust.suppressed',
  'status.success',
  'status.warning',
  'status.error',
  'status.info',
  'surface.error',
  'surface.warning',
  'surface.info',
  'surface.success',
  'surface.sidebar.active',
  'text.sidebar.active',
] as const;

export const SPACING_TOKENS = [4, 8, 12, 16, 24, 32, 48, 64] as const;

export const TYPOGRAPHY_TOKENS = ['h1', 'h2', 'h3', 'body', 'small', 'code'] as const;

export const ELEVATION_TOKENS = ['card', 'drawer', 'modal'] as const;

export const MOTION_TOKENS = [
  'button.hover',
  'drawer.open',
  'modal.open',
  'toast',
  'number.update',
  'skeleton.pulse',
] as const;

export const FOCUS_TOKENS = ['outline.width', 'outline.color', 'outline.offset'] as const;

export const TARGET_SIZE_TOKENS = ['min', 'dense.min', 'icon'] as const;

export const BREAKPOINTS = {
  mobileMax: 767,
  tabletMin: 768,
  tabletMax: 1023,
  desktopMin: 1024,
  desktopMax: 1439,
  wideMin: 1440,
} as const;

export const CSS_VAR_MAP: Record<string, string> = {
  'bg.page': '--sk-color-bg-page',
  'bg.sidebar': '--sk-color-bg-sidebar',
  'bg.header': '--sk-color-bg-header',
  'bg.card': '--sk-color-bg-card',
  'bg.muted': '--sk-color-bg-muted',
  'text.primary': '--sk-color-text-primary',
  'text.secondary': '--sk-color-text-secondary',
  'text.muted': '--sk-color-text-muted',
  'text.inverse': '--sk-color-text-inverse',
  'border.default': '--sk-color-border-default',
  'trust.deterministic': '--sk-color-trust-deterministic',
  'trust.probabilistic': '--sk-color-trust-probabilistic',
  'trust.benchmark': '--sk-color-trust-benchmark',
  'trust.prior': '--sk-color-trust-prior',
  'trust.unavailable': '--sk-color-trust-unavailable',
  'trust.suppressed': '--sk-color-trust-suppressed',
  'status.success': '--sk-color-status-success',
  'status.warning': '--sk-color-status-warning',
  'status.error': '--sk-color-status-error',
  'status.info': '--sk-color-status-info',
  'surface.error': '--sk-color-surface-error',
  'surface.warning': '--sk-color-surface-warning',
  'surface.info': '--sk-color-surface-info',
  'surface.success': '--sk-color-surface-success',
  'surface.sidebar.active': '--sk-color-surface-sidebar-active',
  'text.sidebar.active': '--sk-color-text-sidebar-active',
};

export function getCssVar(tokenName: keyof typeof CSS_VAR_MAP | string): string {
  const key = tokenName as keyof typeof CSS_VAR_MAP;
  const cssVar = CSS_VAR_MAP[key];
  if (!cssVar) {
    throw new Error(`Token missing: ${tokenName}`);
  }
  return `var(${cssVar})`;
}

export function assertTokenRegistryComplete(): void {
  for (const token of COLOR_TOKENS) {
    if (!CSS_VAR_MAP[token]) {
      throw new Error(`Token registry incomplete: ${token}`);
    }
  }
}

/** Parse --sk-* custom properties from tokens.css and verify TS registry alignment */
export function assertTokenCssAlignment(tokensCss: string): void {
  const cssVars = [...tokensCss.matchAll(/(--sk-[a-z0-9-]+):/gi)].map((m) => m[1]);
  const uniqueCssVars = [...new Set(cssVars)];

  for (const token of COLOR_TOKENS) {
    const cssVar = CSS_VAR_MAP[token];
    if (!uniqueCssVars.includes(cssVar)) {
      throw new Error(`CSS missing variable for token ${token}: ${cssVar}`);
    }
  }

  for (const cssVar of Object.values(CSS_VAR_MAP)) {
    if (!uniqueCssVars.includes(cssVar)) {
      throw new Error(`Registry maps missing CSS variable: ${cssVar}`);
    }
  }
}

export function getRequiredColorTokens(exclude?: string): readonly string[] {
  if (!exclude) return COLOR_TOKENS;
  return COLOR_TOKENS.filter((t) => t !== exclude);
}
