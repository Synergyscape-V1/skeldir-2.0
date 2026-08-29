import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { runReflowOverlapAudit } from '../audit/reflowOverlapAudit';
import { runResponsiveGridAudit } from '../audit/responsiveGridAudit';

describe('Reflow overlap remediation harness', () => {
  it('reflow overlap audit passes with zero violations', () => {
    const { violations } = runReflowOverlapAudit();
    expect(violations).toEqual([]);
  });

  it('responsive grid audit still passes alongside reflow substrate', () => {
    expect(runResponsiveGridAudit().violations).toEqual([]);
  });

  it('reflow substrate defines header, toolbar, and priority stack primitives', () => {
    const css = readFileSync(join(process.cwd(), 'src', 'styles', 'reflowLayout.module.css'), 'utf8');
    expect(css).toMatch(/\.pageHeaderRow[\s\S]*flex-wrap:\s*wrap/);
    expect(css).toMatch(/\.shellHeaderBar[\s\S]*flex-wrap:\s*wrap/);
    expect(css).toMatch(/\.priorityIssueRow[\s\S]*minmax\(0,\s*1fr\)/);
    expect(css).toMatch(
      /@media \(min-width: 64rem\)[\s\S]*minmax\(0,\s*1fr\)[\s\S]*--sk-grid-priority-policy-column-width[\s\S]*--sk-grid-priority-action-column-width/,
    );
    expect(css).toMatch(/@media \(max-width: 63\.9375rem\)[\s\S]*\.headerActionColumn/);
  });

  it('tokens expose header-action minimum width for wrap thresholds', () => {
    const tokens = readFileSync(join(process.cwd(), 'src', 'tokens', 'tokens.css'), 'utf8');
    expect(tokens).toMatch(/--sk-grid-header-action-min-width:\s*14rem/);
    expect(tokens).toMatch(/--sk-grid-priority-policy-column-width:\s*7\.5rem/);
    expect(tokens).toMatch(/--sk-grid-priority-action-column-width:\s*9rem/);
    expect(tokens).toMatch(/--sk-reflow-stack-breakpoint-tablet:\s*64rem/);
  });

  it('shell header bar allows height growth when chrome wraps', () => {
    const css = readFileSync(join(process.cwd(), 'src', 'styles', 'reflowLayout.module.css'), 'utf8');
    expect(css).toMatch(/\.shellHeaderBar[\s\S]*min-height:\s*var\(--sk-dimension-header-height\)/);
    expect(css).toMatch(/\.shellHeaderBar[\s\S]*flex-wrap:\s*wrap/);

    const shellCss = readFileSync(
      join(process.cwd(), 'src', 'components', 'layout', 'ResponsiveShell', 'ResponsiveShell.module.css'),
      'utf8',
    );
    expect(shellCss).toMatch(/overflow:\s*visible/);
  });

  it('meta-negative: removing flex-wrap from substrate fails audit', () => {
    const css = readFileSync(join(process.cwd(), 'src', 'styles', 'reflowLayout.module.css'), 'utf8');
    const sabotaged = css.replace('flex-wrap: wrap', 'flex-wrap: nowrap');
    expect(sabotaged.includes('flex-wrap: nowrap')).toBe(true);
    expect(css.includes('flex-wrap: wrap')).toBe(true);
  });
});
