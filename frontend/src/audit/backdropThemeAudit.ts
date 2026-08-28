import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const ROOT = join(import.meta.dirname, '..', '..');

const TOKENS_FILE = 'src/tokens/tokens.css';
const SHELL_CSS = 'src/components/layout/ResponsiveShell/ResponsiveShell.module.css';

const WCAG_AA_NORMAL_TEXT = 4.5;
const WCAG_AA_LARGE_TEXT = 3;

export interface BackdropThemeViolation {
  check: string;
  detail: string;
}

function parseHex(hex: string): [number, number, number] {
  const normalized = hex.replace('#', '').toLowerCase();
  const value =
    normalized.length === 3
      ? normalized
          .split('')
          .map((c) => c + c)
          .join('')
      : normalized;
  return [
    parseInt(value.slice(0, 2), 16),
    parseInt(value.slice(2, 4), 16),
    parseInt(value.slice(4, 6), 16),
  ];
}

function channelLuminance(channel: number): number {
  const s = channel / 255;
  return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
}

export function relativeLuminance(hex: string): number {
  const [r, g, b] = parseHex(hex);
  return 0.2126 * channelLuminance(r) + 0.7152 * channelLuminance(g) + 0.0722 * channelLuminance(b);
}

export function contrastRatio(foregroundHex: string, backgroundHex: string): number {
  const l1 = relativeLuminance(foregroundHex);
  const l2 = relativeLuminance(backgroundHex);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

function readTokenValue(tokensCss: string, name: string): string | null {
  const match = tokensCss.match(new RegExp(`${name}:\\s*(#[0-9a-fA-F]{3,8})`));
  return match?.[1]?.toLowerCase() ?? null;
}

function isDarkerThan(baseHex: string, candidateHex: string): boolean {
  return relativeLuminance(candidateHex) < relativeLuminance(baseHex);
}

function isLighterThan(baseHex: string, candidateHex: string): boolean {
  return relativeLuminance(candidateHex) > relativeLuminance(baseHex);
}

export function runBackdropThemeAudit() {
  const violations: BackdropThemeViolation[] = [];
  const tokensCss = readFileSync(join(ROOT, TOKENS_FILE), 'utf8');
  const shellCss = readFileSync(join(ROOT, SHELL_CSS), 'utf8');

  const page = readTokenValue(tokensCss, '--sk-color-bg-page');
  const sidebar = readTokenValue(tokensCss, '--sk-color-bg-sidebar');
  const header = readTokenValue(tokensCss, '--sk-color-bg-header');
  const card = readTokenValue(tokensCss, '--sk-color-bg-card');
  const textPrimary = readTokenValue(tokensCss, '--sk-color-text-primary');
  const textSecondary = readTokenValue(tokensCss, '--sk-color-text-secondary');
  const textMuted = readTokenValue(tokensCss, '--sk-color-text-muted');

  if (page !== '#faf9f5') {
    violations.push({
      check: 'page-backdrop-ivory',
      detail: `expected --sk-color-bg-page #faf9f5, got ${page ?? 'missing'}`,
    });
  }

  if (!sidebar) {
    violations.push({ check: 'sidebar-token-defined', detail: 'missing --sk-color-bg-sidebar' });
  } else if (page && !isDarkerThan(page, sidebar)) {
    violations.push({
      check: 'sidebar-tonal-step',
      detail: 'sidebar must be subtly darker than page backdrop',
    });
  }

  if (!header) {
    violations.push({ check: 'header-token-defined', detail: 'missing --sk-color-bg-header' });
  } else if (page && header !== page && sidebar && header !== sidebar) {
    violations.push({
      check: 'header-palette-coherence',
      detail: 'header must match page or sidebar warm ivory tone',
    });
  }

  if (!card || !page || !isLighterThan(page, card)) {
    violations.push({
      check: 'card-contrast-on-canvas',
      detail: 'card surfaces must be lighter than page backdrop for boundary separation',
    });
  }

  if (!shellCss.includes('background: var(--sk-color-bg-sidebar)')) {
    violations.push({
      check: 'shell-sidebar-token-wiring',
      detail: 'ResponsiveShell sidebar must use --sk-color-bg-sidebar',
    });
  }

  if (!shellCss.includes('background: var(--sk-color-bg-header)')) {
    violations.push({
      check: 'shell-header-token-wiring',
      detail: 'ResponsiveShell header must use --sk-color-bg-header',
    });
  }

  const contrastChecks: Array<{ check: string; fg: string | null; bg: string | null; min: number }> = [
    { check: 'contrast-primary-on-page', fg: textPrimary, bg: page, min: WCAG_AA_NORMAL_TEXT },
    { check: 'contrast-primary-on-sidebar', fg: textPrimary, bg: sidebar, min: WCAG_AA_NORMAL_TEXT },
    { check: 'contrast-primary-on-card', fg: textPrimary, bg: card, min: WCAG_AA_NORMAL_TEXT },
    { check: 'contrast-secondary-on-page', fg: textSecondary, bg: page, min: WCAG_AA_NORMAL_TEXT },
    { check: 'contrast-muted-on-page', fg: textMuted, bg: page, min: WCAG_AA_LARGE_TEXT },
  ];

  for (const { check, fg, bg, min } of contrastChecks) {
    if (!fg || !bg) {
      violations.push({ check, detail: 'missing foreground or background token for contrast probe' });
      continue;
    }
    const ratio = contrastRatio(fg, bg);
    if (ratio < min) {
      violations.push({
        check,
        detail: `contrast ${ratio.toFixed(2)}:1 below WCAG AA minimum ${min}:1`,
      });
    }
  }

  return {
    violations,
    contrast: {
      primaryOnPage: page && textPrimary ? contrastRatio(textPrimary, page) : null,
      secondaryOnPage: page && textSecondary ? contrastRatio(textSecondary, page) : null,
      mutedOnPage: page && textMuted ? contrastRatio(textMuted, page) : null,
    },
  };
}
