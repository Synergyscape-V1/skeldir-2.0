/**
 * FINAL SINGLE CHANNEL DETAIL — Light-Theme Token System
 *
 * Enterprise-grade light UI: high legibility, restrained contrast,
 * strong information hierarchy, minimal consumer glow.
 *
 * These map to the existing :root CSS custom properties where possible,
 * with Skeldir-specific extensions for confidence, channels, and data.
 */

export const tokens = {
  bg: {
    page: '#FAFBFC',        // Warm off-white page surface
    card: '#FFFFFF',         // Pure white cards
    nested: '#F4F6F8',      // Light grey for nested sections
    elevated: '#EEF1F5',    // Slightly darker for elevated elements
    muted: '#F8F9FA',       // Barely-there surface tint
  },
  text: {
    primary: '#1A1F2E',     // Near-black for primary text
    secondary: '#5A6578',   // Medium grey for secondary
    muted: '#8B95A6',       // Lighter for de-emphasized text
    inverse: '#FFFFFF',     // White on dark surfaces
  },
  brand: '#2563EB',         // Professional blue (aligns with --primary)
  confidence: {
    high: '#059669',        // Emerald — enterprise-safe green
    medium: '#D97706',      // Amber — clear warning without alarm
    low: '#DC2626',         // Red — unmistakable alert
  },
  positive: '#059669',
  negative: '#DC2626',
  neutral: '#D97706',
  border: {
    subtle: 'rgba(0,0,0,0.06)',   // Very light borders
    default: 'rgba(0,0,0,0.10)',  // Standard borders
    strong: 'rgba(0,0,0,0.15)',   // Emphasized borders
  },
  shadow: {
    sm: '0 1px 2px rgba(0,0,0,0.04)',
    md: '0 2px 8px rgba(0,0,0,0.06)',
    lg: '0 4px 16px rgba(0,0,0,0.08)',
  },
  font: {
    heading: "'Syne', sans-serif",
    body: "'IBM Plex Sans', sans-serif",
    mono: "'IBM Plex Mono', monospace",
  },
  motion: {
    micro: '120ms',
    short: '200ms',
    medium: '300ms',
    breathe: '3000ms',
    easing: 'cubic-bezier(0.4, 0, 0.2, 1)',
  },
  radius: {
    sm: '6px',
    md: '8px',
    lg: '12px',
    pill: '9999px',
  },
} as const;

export const CHANNEL_COLORS: Record<string, string> = {
  meta: '#0668E1',
  facebook: '#0668E1',
  google: '#34A853',
  tiktok: '#EE1D52',
  email: '#7C3AED',
  pinterest: '#E60023',
  linkedin: '#0A66C2',
  other: '#6B7280',
  direct: '#6B7280',
};

export const FONT_IMPORT =
  '@import url("https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700&family=IBM+Plex+Sans:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600;700&display=swap");';
