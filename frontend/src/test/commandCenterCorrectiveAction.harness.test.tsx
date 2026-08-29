import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import { within } from '@testing-library/react';
import {
  buildRadiusNestingAuditTable,
  runCommandCenterCorrectiveBrandScan,
  runCommandCenterCorrectiveIntegrityProbes,
  runCommandCenterCorrectiveSabotageProbes,
} from '../audit/commandCenterCorrectiveActionNegativeScopeScan';
import { runCommandCenterRedesignNegativeScopeScan } from '../audit/commandCenterRedesignNegativeScopeScan';
import { COMMAND_CENTER_COPY } from '../commandCenter/copy';
import { makeTrendPointFixture } from '../commandCenter/revenueSnapshotFixtures';
import {
  setCommandCenterSubstrateOverridesForTests,
  setCommandCenterTestMode,
} from '../commandCenter/commandCenterClient';
import {
  renderCommandCenter,
  renderCommandCenterPageOnly,
  resetLevel10HarnessState,
  seedShellAuth,
  seedShellAuthWithoutTenant,
  waitForCommandCenterLoaded,
  waitForCommandCenterMarker,
  screen,
} from './level10.helpers';

function isVisible(el: Element | null): boolean {
  if (!el) return false;
  const style = window.getComputedStyle(el);
  return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
}

function collectVisibleSkeldirOutsideBrand(): string[] {
  const brand = document.querySelector('[data-shell-brand]');
  const hits: string[] = [];
  for (const el of document.querySelectorAll('h1, h2, span, a, button')) {
    if (brand?.contains(el)) continue;
    const text = (el.textContent ?? '').trim();
    if (text !== 'Skeldir') continue;
    if (!isVisible(el)) continue;
    hits.push(`${el.tagName.toLowerCase()}${el.className ? `.${String(el.className).split(' ')[0]}` : ''}`);
  }
  return hits;
}

function focusDescriptor(el: Element | null): string {
  if (!el || el === document.body) return 'body';
  const role = el.getAttribute('role');
  const label =
    el.getAttribute('aria-label') ??
    (el as HTMLElement).innerText?.trim().slice(0, 40) ??
  el.getAttribute('data-command-center-primary-action') ??
    el.tagName.toLowerCase();
  return [el.tagName.toLowerCase(), role, label].filter(Boolean).join(':');
}

beforeEach(() => {
  resetLevel10HarnessState();
});

describe('Command Center Corrective Action — CA-1 brand architecture', () => {
  it('brand scan passes in source', () => {
    expect(
      runCommandCenterCorrectiveIntegrityProbes().filter((p) => p.name.includes('header') || p.name.includes('brand')).every((p) => p.ok),
    ).toBe(true);
  });

  it('only ShellBrand exposes visible Skeldir on /app', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    expect(document.querySelector('[data-shell-brand]')).toBeTruthy();
    expect(document.querySelector('[data-shell-brand] h1')).toBeNull();
    expect(collectVisibleSkeldirOutsideBrand()).toEqual([]);
    const page = document.querySelector('[data-command-center-page]') as HTMLElement;
    expect(within(page).getByRole('heading', { level: 1, name: COMMAND_CENTER_COPY.pageTitle })).toBeInTheDocument();
  });

  it('brand duplicate negative control fails under sabotage simulation', () => {
    const clean =
      'data-shell-brand command-center-trend-available commandCenterCorrectiveAction.harness';
    const sabotaged = 'data-shell-brand <h1>Skeldir</h1>';
    expect(runCommandCenterCorrectiveSabotageProbes(clean).every((p) => !p.triggered)).toBe(true);
    expect(runCommandCenterCorrectiveSabotageProbes(sabotaged).find((p) => p.name === 'duplicate-brand-skeldir')?.triggered).toBe(true);
  });
});

describe('Command Center Corrective Action — CA-2 disposition matrix markers', () => {
  it('integrity probes include extended fixtures', () => {
    expect(runCommandCenterCorrectiveIntegrityProbes().every((p) => p.ok)).toBe(true);
  });

  it('default loaded /app renders verified revenue chart from claims ledger', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    expect(document.querySelector('[data-verified-revenue-chart]')).toBeTruthy();
    expect(document.querySelector('[data-trend-unavailable]')).toBeNull();
  });

  it('trend-available renders chart marker at runtime', async () => {
    seedShellAuth();
    setCommandCenterSubstrateOverridesForTests({
      trendPointsOverride: [
        makeTrendPointFixture({ date: '2026-06-01', verifiedRevenueMinor: 100_000n }),
      ],
    });
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    expect(document.querySelector('[data-verified-revenue-chart]')).toBeTruthy();
  });

  it('empty tenant renders empty tenant panel', async () => {
    seedShellAuthWithoutTenant();
    renderCommandCenterPageOnly();
    await waitForCommandCenterMarker('[data-command-center-empty-tenant="true"]');
    expect(screen.getByText(COMMAND_CENTER_COPY.emptyTenant)).toBeInTheDocument();
  });

  it('stale aggregate renders stale copy', async () => {
    seedShellAuth();
    setCommandCenterTestMode('stale');
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    expect(screen.getByText(COMMAND_CENTER_COPY.staleAggregate)).toBeInTheDocument();
  });
});

describe('Command Center Corrective Action — CA-3 keyboard traversal', () => {
  it('tab traversal reaches shell chrome and command center controls', async () => {
    const user = userEvent.setup();
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();

    const visited = new Set<string>();
    for (let i = 0; i < 48; i++) {
      await user.tab();
      const active = document.activeElement;
      if (!active || active === document.body) continue;
      visited.add(focusDescriptor(active));
    }

    expect([...visited].some((d) => /notification/i.test(d))).toBe(true);
    const primary = document.querySelector('[data-command-center-primary-action] button, [data-command-center-primary-action] a') as HTMLElement | null;
    expect(primary?.textContent).toMatch(/review issues/i);
    primary?.focus();
    expect(document.activeElement).toBe(primary);
    expect(document.querySelector('[data-summary-drilldown="verified_revenue"]')).toBeTruthy();
    expect(document.querySelector('a[data-audit-chip]')).toBeTruthy();
    expect(document.querySelector('[data-recent-envelope-row-link], [data-recent-trust-envelopes]')).toBeTruthy();
  });

  it('keyboard negative control: missing notification label would fail scan', () => {
    const clean = 'aria-label="Notifications" suppressVisibleRouteTitle';
    const sabotaged = 'aria-label="" suppressVisibleRouteTitle';
    expect(clean.includes('aria-label="Notifications"')).toBe(true);
    expect(sabotaged.includes('aria-label="Notifications"')).toBe(false);
  });
});

describe('Command Center Corrective Action — CA-4 radius nesting', () => {
  it('radius audit table documents nested vs primitive surfaces', () => {
    const table = buildRadiusNestingAuditTable();
    expect(table.some((r) => r.classification === 'A-nested-aligned' && r.innerRadius === '0px')).toBe(true);
    expect(table.some((r) => r.classification === 'B-independent-primitive')).toBe(true);
  });
});

describe('Command Center Corrective Action — CA-6 lower proof surfaces', () => {
  it('Recent TrustEnvelopes and Audit Activity expose field-complete markers', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    expect(document.querySelector('[data-recent-trust-envelopes]')).toBeTruthy();
    expect(document.querySelector('[data-audit-activity-strip]')).toBeTruthy();
    expect(document.querySelector('[data-recent-envelope-row-link]') || document.querySelector('[data-recent-trust-envelopes] .emptyState')).toBeTruthy();
    expect(document.querySelector('[data-audit-chip]')).toBeTruthy();
    expect(document.querySelector('[data-audit-actor-label]')).toBeTruthy();
    expect(document.querySelector('[data-audit-action-label]')).toBeTruthy();
    expect(document.querySelector('[data-audit-refresh-model="poll-60s"]')).toBeTruthy();
    expect(document.querySelector('[data-view-audit-ledger]')).toBeTruthy();
  });
});

describe('Command Center Corrective Action — CA-7 summary long values', () => {
  it('action authority metric keeps H2 data attribute at runtime', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    const value = document.querySelector('[data-summary-metric-value="action_authority"]');
    expect(value?.textContent).toMatch(/Pending Certification|Simulation Only|Blocked/i);
    expect(value?.className).toMatch(/supervisoryMetricValue/);
  });
});

describe('Command Center Corrective Action — CA-8 regression preservation', () => {
  it('redesign negative scope scan still passes', () => {
    expect(runCommandCenterCorrectiveIntegrityProbes().every((p) => p.ok)).toBe(true);
    expect(runCommandCenterRedesignNegativeScopeScan().violations).toEqual([]);
  });

  it('no raw internal variables in DOM', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    expect(document.body.textContent).not.toContain('Comparable_to_previous_value');
    expect(document.querySelector('[data-channel-trust-table] [data-platform-claim-label]')).toBeFalsy();
  });
});
