import { describe, expect, it } from 'vitest';
import { runResponsiveGridAudit } from '../audit/responsiveGridAudit';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

describe('Responsive grid harness', () => {
  it('responsive grid audit passes with zero violations', () => {
    const { violations } = runResponsiveGridAudit();
    expect(violations).toEqual([]);
  });

  it('substrate defines auto-fit tile reflow with minimum width tokens', () => {
    const css = readFileSync(join(process.cwd(), 'src', 'styles', 'responsiveGrid.module.css'), 'utf8');
    expect(css).toMatch(/\.tileGrid[\s\S]*repeat\(auto-fit,\s*minmax\(min\(100%,\s*var\(--sk-grid-tile-min-width\)\)/);
    expect(css).toMatch(/\.supervisoryGrid[\s\S]*minmax\(var\(--sk-grid-trend-panel-min-width\)/);
    expect(css).toMatch(/\.filterGrid[\s\S]*--sk-grid-filter-field-min-width/);
  });

  it('tokens expose grid minimum dimension registry', () => {
    const tokens = readFileSync(join(process.cwd(), 'src', 'tokens', 'tokens.css'), 'utf8');
    expect(tokens).toMatch(/--sk-grid-tile-min-width:\s*14rem/);
    expect(tokens).toMatch(/--sk-grid-tile-min-height:\s*9rem/);
    expect(tokens).toMatch(/--sk-grid-trend-panel-min-width:\s*22rem/);
    expect(tokens).toMatch(/--sk-grid-channel-panel-min-width:\s*28rem/);
    expect(tokens).toMatch(/--sk-grid-supervisory-trend-column:\s*11fr/);
    expect(tokens).toMatch(/--sk-grid-supervisory-activity-column:\s*10fr/);
  });
});
