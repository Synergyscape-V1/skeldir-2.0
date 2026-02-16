/**
 * SKELDIR DESIGN TOKEN SYSTEM
 * Single source of truth for all visual decisions.
 *
 * Rule: No component may hardcode a color, spacing, or duration value.
 * All values must reference this file.
 *
 * Derivation: These tokens are the emergent output of synthesizing:
 * - Bayesian confidence semantics (high/medium/low → color)
 * - Dark-surface psychology (agency director 11PM scenario)
 * - Data density rules (dense → neutral, sparse → vibrant)
 * - WCAG AA accessibility (all confidence colors verified ≥4.5:1 on --color-bg-secondary)
 */

// ─────────────────────────────────────────────────────────────────
// COLORS
// ─────────────────────────────────────────────────────────────────

export const colors = {
  // Foundation
  bgPrimary:      '#0A0E1A',
  bgSecondary:    '#111827',
  bgTertiary:     '#1F2937',
  bgElevated:     '#263244',

  // Text
  textPrimary:    '#F0F4FF',
  textSecondary:  '#8B9AB8',
  textMuted:      '#4A5568',
  textInverse:    '#0A0E1A',

  // Borders
  borderSubtle:   'rgba(139, 154, 184, 0.12)',
  borderDefault:  'rgba(139, 154, 184, 0.24)',
  borderStrong:   'rgba(139, 154, 184, 0.48)',

  // Brand
  brandPrimary:   '#3D7BF5',
  brandGlow:      'rgba(61, 123, 245, 0.20)',

  // Bayesian Confidence Spectrum
  confidenceHigh:         '#10D98C',
  confidenceHighBg:       'rgba(16, 217, 140, 0.08)',
  confidenceHighBorder:   'rgba(16, 217, 140, 0.24)',

  confidenceMedium:       '#F5A623',
  confidenceMediumBg:     'rgba(245, 166, 35, 0.08)',
  confidenceMediumBorder: 'rgba(245, 166, 35, 0.24)',

  confidenceLow:          '#F04E4E',
  confidenceLowBg:        'rgba(240, 78, 78, 0.08)',
  confidenceLowBorder:    'rgba(240, 78, 78, 0.24)',

  // Channel Attribution Colors (deterministic map — never reorder)
  channels: {
    1: '#3D7BF5',  // Meta/Facebook
    2: '#10D98C',  // Google
    3: '#F5A623',  // TikTok
    4: '#B36CF5',  // Email
    5: '#F54E8B',  // Pinterest
    6: '#36BFFA',  // LinkedIn
    7: '#FB7C4C',  // Other/Direct
  } as Record<number, string>,

  // Functional
  success:    '#10D98C',
  warning:    '#F5A623',
  error:      '#F04E4E',
  info:       '#3D7BF5',

  // Discrepancy severity
  discrepancySafe:     '#10D98C',  // <5%
  discrepancyWarning:  '#F5A623',  // 5–15%
  discrepancyCritical: '#F04E4E',  // >15%
} as const;

// ─────────────────────────────────────────────────────────────────
// TYPOGRAPHY
// ─────────────────────────────────────────────────────────────────

export const typography = {
  fontHeading: "'Syne', sans-serif",
  fontBody:    "'IBM Plex Sans', sans-serif",
  fontData:    "'IBM Plex Mono', monospace",

  googleFontsUrl: "https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700&family=IBM+Plex+Sans:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600;700&display=swap",

  scale: {
    displayLg:  { size: '48px', weight: 700, lineHeight: 1.1,  font: 'heading', tracking: '-0.02em'  },
    displayMd:  { size: '36px', weight: 700, lineHeight: 1.15, font: 'heading', tracking: '-0.015em' },
    headingLg:  { size: '24px', weight: 600, lineHeight: 1.3,  font: 'heading', tracking: '-0.01em'  },
    headingMd:  { size: '20px', weight: 600, lineHeight: 1.4,  font: 'heading', tracking: '-0.005em' },
    headingSm:  { size: '16px', weight: 600, lineHeight: 1.4,  font: 'heading', tracking: '0'        },
    bodyLg:     { size: '16px', weight: 400, lineHeight: 1.65, font: 'body',    tracking: '0'        },
    bodyMd:     { size: '14px', weight: 400, lineHeight: 1.6,  font: 'body',    tracking: '0'        },
    bodySm:     { size: '12px', weight: 400, lineHeight: 1.5,  font: 'body',    tracking: '0.01em'   },
    // Data variants — all numeric metric values use these
    dataLg:     { size: '36px', weight: 600, lineHeight: 1.0,  font: 'data',    tracking: '-0.02em'  },
    dataMd:     { size: '24px', weight: 600, lineHeight: 1.0,  font: 'data',    tracking: '-0.01em'  },
    dataSm:     { size: '14px', weight: 500, lineHeight: 1.0,  font: 'data',    tracking: '0'        },
    dataXs:     { size: '12px', weight: 400, lineHeight: 1.0,  font: 'data',    tracking: '0.01em'   },
  },
} as const;

// ─────────────────────────────────────────────────────────────────
// SPACING (4px base grid)
// ─────────────────────────────────────────────────────────────────

export const spacing = {
  px:    '1px',
  '0.5': '2px',
  '1':   '4px',
  '1.5': '6px',
  '2':   '8px',
  '3':   '12px',
  '4':   '16px',
  '5':   '20px',
  '6':   '24px',
  '8':   '32px',
  '10':  '40px',
  '12':  '48px',
  '16':  '64px',
  '20':  '80px',
  '24':  '96px',
} as const;

export const radius = {
  sm:   '4px',
  md:   '8px',
  lg:   '12px',
  xl:   '16px',
  full: '9999px',
} as const;

// ─────────────────────────────────────────────────────────────────
// MOTION
// ─────────────────────────────────────────────────────────────────

export const motion = {
  micro:   { duration: '120ms', easing: 'cubic-bezier(0.4, 0, 0.2, 1)' },
  short:   { duration: '200ms', easing: 'cubic-bezier(0.4, 0, 0.2, 1)' },
  medium:  { duration: '300ms', easing: 'cubic-bezier(0.4, 0, 0.6, 1)' },
  long:    { duration: '500ms', easing: 'cubic-bezier(0.4, 0, 0.2, 1)' },
  breathe: { duration: '3000ms', easing: 'cubic-bezier(0.45, 0, 0.55, 1)', iteration: 'infinite' as const, direction: 'alternate' as const },
  pulse:   { duration: '600ms', easing: 'cubic-bezier(0, 0, 0.2, 1)', iteration: 1 },
} as const;

// ─────────────────────────────────────────────────────────────────
// SHADOWS (depth system for dark surface)
// ─────────────────────────────────────────────────────────────────

export const shadows = {
  sm:    '0 1px 3px rgba(0,0,0,0.4)',
  md:    '0 4px 12px rgba(0,0,0,0.5)',
  lg:    '0 12px 32px rgba(0,0,0,0.6)',
  brand: '0 0 24px rgba(61, 123, 245, 0.20)',
  // Confidence glow shadows — used on cards in nominal state
  high:   '0 0 16px rgba(16, 217, 140, 0.12)',
  medium: '0 0 16px rgba(245, 166, 35, 0.12)',
  low:    '0 0 16px rgba(240, 78, 78, 0.12)',
} as const;

// ─────────────────────────────────────────────────────────────────
// BREAKPOINTS
// ─────────────────────────────────────────────────────────────────

export const breakpoints = {
  mobile:  '320px',
  tablet:  '768px',
  desktop: '1024px',
  wide:    '1440px',
} as const;

// ─────────────────────────────────────────────────────────────────
// Z-INDEX SCALE
// ─────────────────────────────────────────────────────────────────

export const zIndex = {
  base:     0,
  above:    10,
  sticky:   20,
  overlay:  30,
  modal:    40,
  toast:    50,
} as const;

// ─────────────────────────────────────────────────────────────────
// DERIVED CONFIDENCE CONFIG (single function for all components)
// ─────────────────────────────────────────────────────────────────

export type ConfidenceLevel = 'high' | 'medium' | 'low';

export function getConfidenceTokens(confidence: ConfidenceLevel) {
  return {
    high: {
      color:          colors.confidenceHigh,
      bg:             colors.confidenceHighBg,
      border:         colors.confidenceHighBorder,
      shadow:         shadows.high,
      label:          'High Confidence',
      icon:           'check-circle',
      breatheScale:   1.02,
      breatheDuration: '4000ms',
    },
    medium: {
      color:          colors.confidenceMedium,
      bg:             colors.confidenceMediumBg,
      border:         colors.confidenceMediumBorder,
      shadow:         shadows.medium,
      label:          'Medium Confidence',
      icon:           'alert-circle',
      breatheScale:   1.10,
      breatheDuration: '2800ms',
    },
    low: {
      color:          colors.confidenceLow,
      bg:             colors.confidenceLowBg,
      border:         colors.confidenceLowBorder,
      shadow:         shadows.low,
      label:          'Low Confidence',
      icon:           'alert-triangle',
      breatheScale:   1.22,
      breatheDuration: '2000ms',
    },
  }[confidence];
}

export function getDiscrepancyTokens(discrepancyPercent: number) {
  const abs = Math.abs(discrepancyPercent);
  if (abs < 5)  return { color: colors.discrepancySafe,     severity: 'safe',     label: `Within noise floor (±${abs.toFixed(1)}%)` };
  if (abs < 15) return { color: colors.discrepancyWarning,  severity: 'warning',  label: `${abs.toFixed(1)}% discrepancy — review source data` };
  return              { color: colors.discrepancyCritical, severity: 'critical', label: `${abs.toFixed(1)}% discrepancy — investigate before decisions` };
}
