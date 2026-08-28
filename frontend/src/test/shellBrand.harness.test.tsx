import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { beforeEach, describe, expect, it } from 'vitest';
import { COMMAND_CENTER_COPY } from '../commandCenter/copy';
import {
  runShellBrandIntegrityProbes,
  runShellBrandSabotageProbes,
} from '../audit/shellBrandNegativeScopeScan';
import {
  renderCommandCenter,
  resetLevel10HarnessState,
  seedShellAuth,
  waitForCommandCenterLoaded,
  screen,
} from './level10.helpers';

function collectVisibleSkeldirOutsideBrand(): string[] {
  const brand = document.querySelector('[data-shell-brand]');
  const hits: string[] = [];
  for (const el of document.querySelectorAll('h1, h2, span, a, button')) {
    if (brand?.contains(el)) continue;
    const text = (el.textContent ?? '').trim();
    if (text !== 'Skeldir') continue;
    const style = window.getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') continue;
    hits.push(el.tagName.toLowerCase());
  }
  return hits;
}

function rectsOverlap(
  a: { top: number; bottom: number; left: number; right: number },
  b: { top: number; bottom: number; left: number; right: number },
): boolean {
  return a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
}

beforeEach(() => {
  resetLevel10HarnessState();
});

describe('Shell brand forensic harness — source integrity', () => {
  it('integrity probes pass for wordmark asset and shell column layout', () => {
    const failed = runShellBrandIntegrityProbes().filter((p) => !p.ok);
    expect(failed).toEqual([]);
  });

  it('sabotage probes detect removed wordmark and header-over-sidebar regression', () => {
    const triggered = runShellBrandSabotageProbes().filter((p) => p.triggered);
    expect(triggered).toEqual([]);
  });
});

describe('Shell brand forensic harness — runtime DOM', () => {
  it('harnesses approved wordmark.svg with shield-dominant lockup proportions', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();

    const brand = document.querySelector('[data-shell-brand]');
    expect(brand).toBeTruthy();

    const wordmark = document.querySelector('[data-shell-brand-wordmark]') as HTMLImageElement | null;
    expect(wordmark).toBeTruthy();
    expect(wordmark?.getAttribute('src') ?? '').toMatch(/wordmark/i);
    expect(Number(wordmark?.getAttribute('height'))).toBeLessThanOrEqual(24);

    const shield = document.querySelector('[data-shell-brand-shield]') as HTMLImageElement | null;
    expect(shield).toBeTruthy();
    expect(Number(shield?.getAttribute('width'))).toBeGreaterThanOrEqual(52);
    expect(Number(shield?.getAttribute('height'))).toBeGreaterThanOrEqual(52);
    expect(Number(shield?.getAttribute('width'))).toBeGreaterThan(Number(wordmark?.getAttribute('height')));

    const tokens = readFileSync(join(process.cwd(), 'src', 'tokens', 'tokens.css'), 'utf8');
    expect(tokens).toMatch(/--sk-dimension-sidebar-brand-lockup-pull:\s*0px/);
    expect(tokens).toMatch(/--sk-dimension-sidebar-brand-lockup-wordmark-offset-y:\s*0px/);
  });

  it('centers page content within the main column', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();

    const mainColumn = document.querySelector('[data-shell-main-column]');
    const contentRail = document.querySelector('[data-page-content-rail]');
    expect(mainColumn).toBeTruthy();
    expect(contentRail).toBeTruthy();

    const mainColumnRect = mainColumn!.getBoundingClientRect();
    const railRect = contentRail!.getBoundingClientRect();
    const leftInset = railRect.left - mainColumnRect.left;
    const rightInset = mainColumnRect.right - railRect.right;
    expect(Math.abs(leftInset - rightInset)).toBeLessThanOrEqual(2);
  });

  it('mounts notification control on sidebar brand wordmark cluster', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();

    expect(document.querySelector('[data-shell-brand-notification-corner]')).toBeTruthy();
    expect(document.querySelector('[data-shell-brand] [data-notification-bell]')).toBeTruthy();
  });

  it('renders shell header with interface location beside sidebar toggle', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();

    expect(document.querySelector('[data-shell-header-column]')).toBeTruthy();
    expect(document.querySelector('[data-shell-header] [data-interface-location]')).toBeTruthy();
    expect(document.querySelector('[data-shell-header] [data-sidebar-toggle]')).toBeTruthy();
  });

  it('sidebar brand occupies sidebar column without main-column overlap', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();

    expect(document.querySelector('[data-shell-sidebar-column]')).toBeTruthy();
    expect(document.querySelector('[data-shell-main-column]')).toBeTruthy();

    const brand = document.querySelector('[data-shell-brand]');
    const sidebarColumn = document.querySelector('[data-shell-sidebar-column]');
    expect(brand).toBeTruthy();
    expect(sidebarColumn?.contains(brand ?? null)).toBe(true);
  });

  it('preserves CA-1 brand architecture on Command Center', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();

    expect(document.querySelector('[data-shell-brand] h1')).toBeNull();
    expect(collectVisibleSkeldirOutsideBrand()).toEqual([]);
    expect(
      screen.getByRole('heading', { level: 1, name: COMMAND_CENTER_COPY.pageTitle }),
    ).toBeInTheDocument();
  });
});
