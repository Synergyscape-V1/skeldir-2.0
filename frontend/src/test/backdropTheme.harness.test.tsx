import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { contrastRatio, runBackdropThemeAudit } from '../audit/backdropThemeAudit';
import { assertTokenCssAlignment, COLOR_TOKENS } from '../tokens';

describe('Warm ivory backdrop theme harness', () => {
  it('backdrop theme audit passes with zero violations', () => {
    const { violations } = runBackdropThemeAudit();
    expect(violations).toEqual([]);
  });

  it('token registry includes sidebar and header backdrop roles', () => {
    expect(COLOR_TOKENS).toContain('bg.sidebar');
    expect(COLOR_TOKENS).toContain('bg.header');
    const css = readFileSync(join(process.cwd(), 'src', 'tokens', 'tokens.css'), 'utf8');
    expect(() => assertTokenCssAlignment(css)).not.toThrow();
    expect(css).toMatch(/--sk-color-bg-page:\s*#faf9f5/);
    expect(css).toMatch(/--sk-color-bg-card:\s*#ffffff/);
  });

  it('primary and secondary text meet WCAG AA on ivory canvas', () => {
    const primary = contrastRatio('#0f172a', '#faf9f5');
    const secondary = contrastRatio('#475569', '#faf9f5');
    const muted = contrastRatio('#64748b', '#faf9f5');
    expect(primary).toBeGreaterThanOrEqual(4.5);
    expect(secondary).toBeGreaterThanOrEqual(4.5);
    expect(muted).toBeGreaterThanOrEqual(3);
  });

  it('sidebar is subtly darker than page without breaking warm palette', () => {
    const pageL = contrastRatio('#0f172a', '#faf9f5');
    const sidebarL = contrastRatio('#0f172a', '#f6f4ef');
    expect(pageL).toBeGreaterThan(sidebarL);
    expect(sidebarL).toBeGreaterThanOrEqual(4.5);
  });

  it('cards remain lighter than canvas for component boundaries', () => {
    const { contrast } = runBackdropThemeAudit();
    expect(contrast.primaryOnPage).toBeGreaterThanOrEqual(4.5);
    const cardVsPage = contrastRatio('#ffffff', '#faf9f5');
    expect(cardVsPage).toBeGreaterThan(1);
  });
});
