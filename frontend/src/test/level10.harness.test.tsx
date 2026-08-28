import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import userEvent from '@testing-library/user-event';
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import { waitFor, act, within } from '@testing-library/react';
import { runLevel9NegativeScopeScan } from '../audit/level9NegativeScopeScan';
import {
  assertLevel10ComponentsExist,
  runLevel10IntegrityProbes,
  runLevel10NegativeScopeScan,
  runLevel10SabotageProbes,
  runLevel10SourceIntegrityProbes,
  runLevel10SourceSabotageProbes,
} from '../audit/level10NegativeScopeScan';
import { runPrivacyScan } from '../audit/privacyScan';
import { runSecretScan } from '../audit/secretScan';
import { runDensityTokenAudit } from '../audit/densityAudit';
import { COMMAND_CENTER_COPY } from '../commandCenter/copy';
import { COMMAND_CENTER_RECENT_ENVELOPES } from '../commandCenter/commandCenterEnvelopeFixtures';
import {
  MAX_PRIORITY_ROWS,
  setCommandCenterTestMode,
  setCommandCenterSubstrateOverridesForTests,
  setCommandCenterDelayForTests,
  setCommandCenterHealthStateForTests,
  resetCommandCenterTestMode,
  getDefaultCommandCenterClient,
  resolvePrimaryAction,
} from '../commandCenter/commandCenterClient';
import { makeTrendPointFixture } from '../commandCenter/revenueSnapshotFixtures';
import type { AuditActivityChip, ChannelTrustRow, PriorityIssue, RecentEnvelopeRow } from '../commandCenter/types';
import { createMockTenant } from '../auth/authClient';
import {
  renderCommandCenter,
  renderCommandCenterPageOnly,
  resetLevel10HarnessState,
  seedShellAuth,
  seedShellAuthWithoutTenant,
  setDesktopViewport1280,
  setDesktopViewport1440,
  resetViewport,
  waitForCommandCenterLoaded,
  waitForCommandCenterMarker,
  screen,
} from './level10.helpers';
import { setMobileViewport375 } from './level9.helpers';

beforeEach(() => {
  vi.useRealTimers();
  resetLevel10HarnessState();
});

afterEach(() => {
  vi.useRealTimers();
  setCommandCenterDelayForTests(0);
});

describe('Level 10 Harness — Scope and regression', () => {
  it('Level 9 scope scan still passes', () => {
    expect(runLevel9NegativeScopeScan().violations).toEqual([]);
  });

  it('Level 10 scope scan passes', () => {
    expect(runLevel10NegativeScopeScan().violations).toEqual([]);
  });

  it('Level 10 components and markers exist', () => {
    expect(assertLevel10ComponentsExist()).toEqual({ ok: true, missing: [] });
  });

  it('Level 10 integrity probes pass', () => {
    const probes = runLevel10IntegrityProbes();
    const sourceProbes = runLevel10SourceIntegrityProbes();
    expect(probes.every((p) => p.ok)).toBe(true);
    expect(sourceProbes.every((p) => p.ok)).toBe(true);
  });

  it('privacy and secret scans pass', () => {
    expect(runPrivacyScan().violations).toEqual([]);
    expect(runSecretScan().violations).toEqual([]);
  });

  it('enterprise compact density token audit passes', () => {
    expect(runDensityTokenAudit().violations).toEqual([]);
  });
});

describe('Level 10 Harness — /app activation', () => {
  it('renders Overview at /app with session and tenant', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    const page = document.querySelector('[data-command-center-page]') as HTMLElement;
    expect(within(page).getByRole('heading', { level: 1, name: COMMAND_CENTER_COPY.pageTitle })).toBeInTheDocument();
    expect(document.querySelector('[data-command-center-page]')).toBeTruthy();
    expect(screen.queryByText(/not the Overview/i)).toBeNull();
  });
});

describe('Level 10 Harness — aggregate contract', () => {
  it('aggregate includes source trace from substrate clients', async () => {
    seedShellAuth();
    const tenant = createMockTenant();
    const outcome = await getDefaultCommandCenterClient().fetchAggregate(tenant.tenantId);
    expect(['loaded', 'stale', 'partial']).toContain(outcome.kind);
    if (outcome.kind === 'loaded' || outcome.kind === 'stale' || outcome.kind === 'partial') {
      expect(outcome.aggregate.sourceTrace.summary).toContain('claims_ledger');
      expect(outcome.aggregate.summaryMetrics.every((m) => m.tileKind)).toBe(true);
      expect(
        outcome.aggregate.summaryMetrics.filter((m) => m.tileKind === 'financial_truth').length,
      ).toBe(2);
    }
  });

  it('cross-tenant leak fails closed', async () => {
    seedShellAuth();
    setCommandCenterTestMode('cross_tenant_leak');
    const tenant = createMockTenant();
    const outcome = await getDefaultCommandCenterClient().fetchAggregate(tenant.tenantId);
    expect(outcome.kind).toBe('permission_denied');
  });
});

describe('Level 10 Harness — priority queue', () => {
  it('sorts by backend severity rank when multiple issues present', async () => {
    const user = userEvent.setup();
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    await user.click(screen.getByRole('button', { name: COMMAND_CENTER_COPY.reviewIssues(3) }));
    await waitFor(() => expect(document.querySelector('[data-priority-queue-modal]')).toBeTruthy());
    const rows = document.querySelectorAll('[data-priority-queue-modal] [data-priority-severity]');
    const ranks: Record<string, number> = {
      policy_approval_required: 1,
      verified_discrepancy_over_threshold: 2,
      confidence_unavailable_where_action_requested: 3,
      benchmark_source_transition: 4,
      integration_degraded: 5,
    };
    const severities = Array.from(rows).map((r) => r.getAttribute('data-priority-severity') ?? '');
    for (let i = 1; i < severities.length; i++) {
      const prev = ranks[severities[i - 1]!] ?? 99;
      const cur = ranks[severities[i]!] ?? 99;
      expect(prev).toBeLessThanOrEqual(cur);
    }
  });

  it('priority queue modal exposes supervisory projection deep links', async () => {
    const user = userEvent.setup();
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    await user.click(screen.getByRole('button', { name: COMMAND_CENTER_COPY.reviewIssues(3) }));
    await waitFor(() => expect(document.querySelector('[data-priority-queue-modal]')).toBeTruthy());
    const top = document.querySelector('[data-top-priority-issue]');
    expect(top?.getAttribute('data-priority-subject-ref')).toBe('sim_0002');
    expect(top?.querySelector('[data-priority-action-href]')?.getAttribute('data-priority-action-href')).toBe(
      '/app/budget/sim_0002?focus=policy&source=command_center_queue&issueId=pri_policy_meta_budget&issueIndex=1&issueTotal=3',
    );
    const discrepancy = document.querySelector('[data-priority-issue="pri_google_discrepancy"]');
    expect(discrepancy?.querySelector('[data-priority-action-href]')?.getAttribute('data-priority-action-href')).toBe(
      '/app/claims/claim_0010?source=command_center_queue&issueId=pri_google_discrepancy&issueIndex=2&issueTotal=3',
    );
    expect(screen.getByText(COMMAND_CENTER_COPY.priorityIssues.googleDiscrepancyExplanation)).toBeInTheDocument();
  });

  it('empty priority state uses view_latest_envelope primary action (no inline queue)', async () => {
    seedShellAuth();
    setCommandCenterTestMode('no_priority');
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    expect(document.querySelector('[data-priority-queue]')).toBeNull();
    expect(document.querySelector('[data-command-center-primary-action]')?.getAttribute('data-primary-action-kind')).toBe(
      'view_latest_envelope',
    );
  });
});

describe('Level 10 Harness — primary action rule', () => {
  it('exactly one primary action in header', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    expect(document.querySelectorAll('[data-command-center-primary-action] button, [data-command-center-primary-action] a').length).toBe(1);
  });

  it('no envelope still exposes View latest TrustEnvelope CTA with onboarding panel', async () => {
    seedShellAuth();
    setCommandCenterTestMode('no_envelope');
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    expect(document.querySelector('[data-command-center-primary-action]')?.getAttribute('data-primary-action-kind')).toBe(
      'view_latest_envelope',
    );
    expect(document.querySelector('[data-command-center-onboarding-panel]')).toBeTruthy();
  });

  it('view_latest_envelope when no priorities and envelope exists', async () => {
    seedShellAuth();
    setCommandCenterTestMode('no_priority');
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    expect(document.querySelector('[data-command-center-primary-action]')?.getAttribute('data-primary-action-kind')).toBe(
      'view_latest_envelope',
    );
  });

  it('review_issues when priorities exist on default load', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    const primary = document.querySelector('[data-command-center-primary-action]');
    expect(primary?.getAttribute('data-primary-action-kind')).toBe('review_issues');
    expect(screen.getByRole('button', { name: COMMAND_CENTER_COPY.reviewIssues(3) })).toBeInTheDocument();
    expect(primary?.querySelector('a')).toBeNull();
    expect(document.querySelector('[data-priority-queue-open]')).toBeTruthy();
  });
});

describe('Level 10 Harness — trend truth boundary', () => {
  it('trend section exposes accessible summary', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    expect(document.querySelector('[data-trend-accessible-summary]')).toBeTruthy();
  });

  it('unavailable trend uses explicit unavailable panel', async () => {
    seedShellAuth();
    setCommandCenterTestMode('trend_unavailable');
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    expect(document.querySelector('[data-verified-revenue-trend]')).toBeTruthy();
  });
});

describe('Level 10 Harness — reconstruction paths', () => {
  it('channel rows link to channel detail', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    expect(document.querySelector('[data-channel-trust-row-link]')).toBeTruthy();
    expect(document.querySelector('[data-channel-trust-table] [data-table-row-interactive]')).toBeTruthy();
  });

  it('recent envelopes and audit strip link correctly', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    expect(document.querySelector('[data-recent-envelope-row-link]')).toBeTruthy();
    expect(document.querySelector('[data-view-audit-ledger]')).toBeTruthy();
    expect(document.querySelector('[data-audit-chip]')).toBeTruthy();
  });

  it('clicking fixture recent envelope row opens claim detail without route recovery', async () => {
    const user = userEvent.setup();
    seedShellAuth();
    setCommandCenterSubstrateOverridesForTests({
      recentEnvelopesOverride: [COMMAND_CENTER_RECENT_ENVELOPES[1]!],
    });
    const { router } = renderCommandCenter('/app');
    await waitForCommandCenterLoaded();

    const trustRow = document.querySelector('[data-recent-envelope-row-link]') as HTMLTableRowElement;
    expect(trustRow?.getAttribute('data-recent-envelope')).toBe('env_0102');

    await user.click(trustRow);
    await waitFor(() => expect(router.state.location.pathname).toBe('/app/claims/claim_0102'));
    await waitFor(() => expect(document.querySelector('[data-claim-detail-loaded]')).toBeTruthy());
    expect(document.querySelector('[data-claim-trust-envelope-drawer]')).toBeNull();
    expect(document.querySelector('[data-route-recovery-panel]')).toBeNull();
  });
});

describe('Level 10 Harness — health and error states', () => {
  it('Trust API read failure banner', async () => {
    seedShellAuth();
    setCommandCenterTestMode('trust_api_failed');
    renderCommandCenter('/app');
    await waitFor(() => expect(document.querySelector('[data-command-center-trust-api-error]')).toBeTruthy());
    expect(screen.getByText(COMMAND_CENTER_COPY.trustApiReadFailed)).toBeInTheDocument();
  });

  it('kill switch read-only banner', async () => {
    seedShellAuth();
    setCommandCenterTestMode('kill_switch');
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    expect(document.querySelector('[data-command-center-kill-switch-banner]')).toBeTruthy();
  });

  it('stale aggregate status text', async () => {
    seedShellAuth();
    setCommandCenterTestMode('stale');
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    expect(screen.getByText(COMMAND_CENTER_COPY.staleAggregate)).toBeInTheDocument();
  });

  it('partial aggregate shows partial status and loaded surface', async () => {
    seedShellAuth();
    setCommandCenterTestMode('partial');
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    expect(screen.getByText(COMMAND_CENTER_COPY.partialAggregate)).toBeInTheDocument();
    expect(document.querySelector('[data-command-center-loaded="true"]')).toBeTruthy();
  });

  it('loading retry appears after over_8s delay', async () => {
    vi.useFakeTimers();
    setCommandCenterDelayForTests(12_000);
    seedShellAuth();
    renderCommandCenter('/app');
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2500);
    });
    expect(screen.getByText(COMMAND_CENTER_COPY.loadingProgress)).toBeInTheDocument();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(6000);
    });
    expect(document.querySelector('[data-command-center-loading-retry]')).toBeTruthy();
  });

  it('confidence_degraded health banner', async () => {
    seedShellAuth();
    setCommandCenterHealthStateForTests('confidence_degraded');
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    expect(
      document.querySelector('[data-command-center-health-banner][data-health-state="confidence_degraded"]'),
    ).toBeTruthy();
    expect(screen.getByText(COMMAND_CENTER_COPY.confidenceDegradedBanner)).toBeInTheDocument();
  });

  it('integration_attention health banner', async () => {
    seedShellAuth();
    setCommandCenterHealthStateForTests('integration_attention');
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    expect(
      document.querySelector('[data-command-center-health-banner][data-health-state="integration_attention"]'),
    ).toBeTruthy();
  });

  it('empty tenant shows workspace required panel', async () => {
    seedShellAuthWithoutTenant();
    renderCommandCenterPageOnly();
    await waitForCommandCenterMarker('[data-command-center-empty-tenant="true"]');
    expect(screen.getByText(COMMAND_CENTER_COPY.emptyTenant)).toBeInTheDocument();
  });

  it('Trust API retry reloads aggregate', async () => {
    const user = userEvent.setup();
    seedShellAuth();
    setCommandCenterTestMode('trust_api_failed');
    renderCommandCenter('/app');
    await waitFor(() => expect(document.querySelector('[data-command-center-trust-api-error]')).toBeTruthy());
    resetCommandCenterTestMode();
    await user.click(screen.getByRole('button', { name: COMMAND_CENTER_COPY.retryAggregate }));
    await waitForCommandCenterLoaded();
    expect(document.querySelector('[data-command-center-loaded="true"]')).toBeTruthy();
  });
});

describe('Level 10 Harness — substrate mutation', () => {
  it('verified revenue changes when substrate override mutates claims total', async () => {
    seedShellAuth();
    const tenant = createMockTenant();
    const client = getDefaultCommandCenterClient();
    const baseline = await client.fetchAggregate(tenant.tenantId);
    expect(baseline.kind).toBe('loaded');
    const baseRevenue = baseline.aggregate.summaryMetrics.find((m) => m.id === 'verified_revenue')?.valueMinor;
    setCommandCenterSubstrateOverridesForTests({ verifiedRevenueBonus: 12_345n });
    const mutated = await client.fetchAggregate(tenant.tenantId);
    expect(mutated.kind).toBe('loaded');
    const nextRevenue = mutated.aggregate.summaryMetrics.find((m) => m.id === 'verified_revenue')?.valueMinor;
    expect(nextRevenue).toBe((baseRevenue ?? 0n) + 12_345n);
  });

  it('trend mutation changes verified revenue trend points independently of summary bonus', async () => {
    seedShellAuth();
    const tenant = createMockTenant();
    const client = getDefaultCommandCenterClient();
    const seedPoints = [makeTrendPointFixture({ date: '2026-06-01', verifiedRevenueMinor: 1_000n })];
    setCommandCenterSubstrateOverridesForTests({ trendPointsOverride: seedPoints });
    const baseline = await client.fetchAggregate(tenant.tenantId);
    expect(baseline.kind).toBe('loaded');
    expect(baseline.aggregate.trendPoints).toHaveLength(1);
    const baseTrendTotal = baseline.aggregate.trendPoints[0]!.verifiedRevenueMinor;
    setCommandCenterSubstrateOverridesForTests({
      trendPointsOverride: seedPoints,
      trendVerifiedBonus: 500n,
    });
    const mutated = await client.fetchAggregate(tenant.tenantId);
    expect(mutated.kind).toBe('loaded');
    expect(mutated.aggregate.trendPoints[0]!.verifiedRevenueMinor).toBe(baseTrendTotal + 500n);
    const baseRevenue = baseline.aggregate.summaryMetrics.find((m) => m.id === 'verified_revenue')?.valueMinor;
    const nextRevenue = mutated.aggregate.summaryMetrics.find((m) => m.id === 'verified_revenue')?.valueMinor;
    expect(nextRevenue).toBe(baseRevenue);
  });

  it('channel mutation changes channel table rows', async () => {
    seedShellAuth();
    const tenant = createMockTenant();
    const client = getDefaultCommandCenterClient();
    const channelOverride: ChannelTrustRow = {
      rowId: 'channel_mutation_test',
      channelId: 'channel_mutation_test',
      axisLabel: 'Mutation Test Channel',
      claimSource: 'google_ads',
      campaignClass: 'paid_search',
      commerceRail: 'organic',
      detailHref: '/app/channels?expand=channel_mutation_test',
      verifiedRevenueMinor: 99_000n,
      currencyCode: 'USD',
      discrepancyRateBps: 100,
      modelAgreementTier: 'medium',
      benchmarkValue: null,
      benchmarkEvidenceClass: 'unavailable',
      benchmarkUnavailableReason: 'Mutation test suppression.',
      policyAuthority: 'blocked',
    };
    setCommandCenterSubstrateOverridesForTests({ channelRowsOverride: [channelOverride] });
    const mutated = await client.fetchAggregate(tenant.tenantId);
    expect(mutated.kind).toBe('loaded');
    expect(mutated.aggregate.channelRows).toHaveLength(1);
    expect(mutated.aggregate.channelRows[0]?.channelId).toBe('channel_mutation_test');
    expect(mutated.aggregate.channelRows[0]?.axisLabel).toBe('Mutation Test Channel');
  });

  it('health mutation changes health state and priority issue set', async () => {
    seedShellAuth();
    const tenant = createMockTenant();
    const client = getDefaultCommandCenterClient();
    const baseline = await client.fetchAggregate(tenant.tenantId);
    expect(baseline.kind).toBe('loaded');
    setCommandCenterSubstrateOverridesForTests({ forceHealthState: 'integration_attention' });
    const mutated = await client.fetchAggregate(tenant.tenantId);
    expect(mutated.kind).toBe('loaded');
    expect(mutated.aggregate.healthState).toBe('integration_attention');
    expect(
      mutated.aggregate.priorityIssues.some((issue) => issue.severity === 'integration_degraded'),
    ).toBe(true);
    expect(baseline.aggregate.healthState).not.toBe('integration_attention');
  });

  it('audit mutation changes audit activity strip', async () => {
    seedShellAuth();
    const tenant = createMockTenant();
    const client = getDefaultCommandCenterClient();
    const auditOverride: AuditActivityChip[] = [
      {
        eventId: 'evt_mutation_test',
        eventType: 'artifact_exported',
        occurredAt: '2026-06-29T12:00:00.000Z',
        tier: 'tier_b',
        actorKind: 'user',
        actorDisplay: 'mutation@acme.example',
        actorClientId: 'usr_mutation_test',
        targetRef: 'env_mutation',
        envelopeId: 'env_mutation',
      },
    ];
    setCommandCenterSubstrateOverridesForTests({ auditActivityOverride: auditOverride });
    const mutated = await client.fetchAggregate(tenant.tenantId);
    expect(mutated.kind).toBe('loaded');
    expect(mutated.aggregate.auditActivity).toHaveLength(1);
    expect(mutated.aggregate.auditActivity[0]?.eventId).toBe('evt_mutation_test');
    expect(mutated.aggregate.auditActivity[0]?.eventType).toBe('artifact_exported');
  });

  it('TrustEnvelope mutation changes recent envelope row and primary action', async () => {
    seedShellAuth();
    const tenant = createMockTenant();
    const client = getDefaultCommandCenterClient();
    const envelopeOverride: RecentEnvelopeRow = {
      envelopeId: 'env_0199',
      subjectRef: 'subject_mutation_test',
      matchVerdict: 'matched_confirmed',
      verifiedRevenueMinor: 100_00n,
      currencyCode: 'USD',
      discrepancyRateBps: 50,
      policyAuthority: 'blocked',
      trustSignal: null,
      createdAt: new Date().toISOString(),
      auditReference: 'aud_mutation_test',
    };
    setCommandCenterTestMode('no_priority');
    setCommandCenterSubstrateOverridesForTests({
      recentEnvelopesOverride: [envelopeOverride],
      latestEnvelopeIdOverride: 'env_0199',
      hasTrustEnvelopeOverride: true,
    });
    const mutated = await client.fetchAggregate(tenant.tenantId);
    expect(mutated.kind).toBe('loaded');
    expect(mutated.aggregate.recentEnvelopes[0]?.envelopeId).toBe('env_0199');
    const action = resolvePrimaryAction(mutated.aggregate);
    expect(action.kind).toBe('view_latest_envelope');
    expect(action.href).toBe('/app/claims/claim_0199?trustEnvelope=env_0199');
  });
});

describe('Level 10 Harness — role boundaries', () => {
  it('billing_only role fails closed with permission denied', async () => {
    seedShellAuth('billing_only');
    renderCommandCenter('/app');
    await waitFor(() => expect(document.querySelector('[data-command-center-page]')).toBeTruthy());
    const page = document.querySelector('[data-command-center-page]') as HTMLElement;
    expect(within(page).queryByRole('heading', { level: 1, name: COMMAND_CENTER_COPY.pageTitle })).toBeNull();
  });

  it('viewer unsafe affordance omits supervisory primary and priority action links', async () => {
    const user = userEvent.setup();
    seedShellAuth('viewer');
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    const page = document.querySelector('[data-command-center-page]') as HTMLElement;
    expect(within(page).getByRole('heading', { level: 1, name: COMMAND_CENTER_COPY.pageTitle })).toBeInTheDocument();
    expect(document.querySelector('[data-command-center-loaded="true"]')).toBeTruthy();
    expect(document.querySelector('[data-command-center-primary-action] a')).toBeNull();
    expect(document.querySelector('[data-viewer-read-only-supervisory]')).toBeTruthy();
    expect(screen.getByText(COMMAND_CENTER_COPY.viewerReadOnlySupervisory)).toBeInTheDocument();
    expect(document.querySelectorAll('[data-priority-action-link]').length).toBe(0);
    await user.click(screen.getByRole('button', { name: COMMAND_CENTER_COPY.viewIssuesReadOnly(3) }));
    await waitFor(() => expect(document.querySelector('[data-priority-queue-modal]')).toBeTruthy());
    expect(document.querySelectorAll('[data-priority-modal-action], [data-priority-drawer-action]').length).toBe(0);
    expect(document.querySelectorAll('[data-priority-modal-source], [data-priority-drawer-source]').length).toBeGreaterThan(0);
    expect(document.querySelector('a[href^="/app/channels"]')).toBeTruthy();
  });
});

describe('Level 10 Harness — unsorted priority injection', () => {
  const unsortedFixture: PriorityIssue[] = [
    {
      id: 'issue-integration-last',
      severity: 'integration_degraded',
      title: 'Integration degraded',
      explanation: 'Connection health requires attention.',
      subjectRef: 'integration_health',
      policyAuthority: 'blocked',
      actionLabel: 'Review integrations',
      actionHref: '/app/integrations',
      sourceLink: '/app/integrations',
    },
    {
      id: 'issue-policy-first',
      severity: 'policy_approval_required',
      title: 'Pending Certification',
      explanation: 'A governed action awaits certification.',
      subjectRef: 'sim_0001',
      policyAuthority: 'approval_required',
      actionLabel: 'Review policy',
      actionHref: '/app/settings/policy',
      sourceLink: '/app/settings/policy',
    },
  ];

  it('unsorted priority input sorts by severity and opens review_issues drawer CTA', async () => {
    const user = userEvent.setup();
    seedShellAuth();
    setCommandCenterSubstrateOverridesForTests({ priorityIssuesUnsorted: unsortedFixture });
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    const primary = document.querySelector('[data-command-center-primary-action]');
    expect(primary?.getAttribute('data-primary-action-kind')).toBe('review_issues');
    expect(primary?.querySelector('button[data-priority-queue-open]')).toBeTruthy();
    expect(primary?.querySelector('a')).toBeNull();
    await user.click(screen.getByRole('button', { name: /Review issues/i }));
    await waitFor(() => expect(document.querySelector('[data-priority-queue-modal]')).toBeTruthy());
    const top = document.querySelector('[data-top-priority-issue]');
    expect(top?.getAttribute('data-top-priority-issue')).toBe('issue-policy-first');
    expect(top?.getAttribute('data-priority-severity')).toBe('policy_approval_required');
    const rows = document.querySelectorAll('[data-priority-queue-modal] [data-priority-severity]');
    expect(rows[0]?.getAttribute('data-priority-severity')).toBe('policy_approval_required');
    expect(rows[1]?.getAttribute('data-priority-severity')).toBe('integration_degraded');
    const topActionHref = top?.querySelector('[data-priority-action-href]')?.getAttribute('data-priority-action-href');
    expect(topActionHref).toContain('/app/settings/policy');
    expect(topActionHref).toContain('source=command_center_queue');
  });
});

describe('Level 10 Harness — accessibility and layout', () => {
  it('audit chip href includes forensic deep-link filters', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    const auditLink = document.querySelector('a[data-audit-chip]');
    expect(auditLink?.getAttribute('href')).toBe('/app/audit/events/evt_artifact_export_01');
  });

  it('keyboard Enter activates channel trust snapshot row', async () => {
    const user = userEvent.setup();
    seedShellAuth();
    const { router } = renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    const channelRow = document.querySelector('[data-channel-trust-row-link]') as HTMLTableRowElement;
    expect(channelRow).toBeTruthy();
    channelRow.focus();
    await user.keyboard('{Enter}');
    await waitFor(() => expect(router.state.location.pathname).toBe('/app/channels'));
    await waitFor(() => expect(router.state.location.search).toMatch(/expand=/));
  });

  it('keyboard Enter activates recent envelope claim detail link', async () => {
    const user = userEvent.setup();
    seedShellAuth();
    const { router } = renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    const trustRow = document.querySelector('[data-recent-envelope-row-link]') as HTMLTableRowElement;
    expect(trustRow).toBeTruthy();
    trustRow.focus();
    await user.keyboard('{Enter}');
    await waitFor(() => expect(router.state.location.pathname).toMatch(/^\/app\/claims\/claim_/));
    await waitFor(() => expect(document.querySelector('[data-claim-detail-loaded]')).toBeTruthy());
    expect(document.querySelector('[data-claim-trust-envelope-drawer]')).toBeNull();
    expect(document.querySelector('[data-route-recovery-panel]')).toBeNull();
  });

  it('keyboard Enter activates audit chip reconstruction link', async () => {
    const user = userEvent.setup();
    seedShellAuth();
    const { router } = renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    const auditLink = document.querySelector('a[data-audit-chip]') as HTMLAnchorElement;
    expect(auditLink).toBeTruthy();
    auditLink.focus();
    await user.keyboard('{Enter}');
    await waitFor(() => expect(router.state.location.pathname).toBe('/app/audit/events/evt_artifact_export_01'));
  });

  it('keyboard Enter activates View Audit Ledger link', async () => {
    const user = userEvent.setup();
    seedShellAuth();
    const { router } = renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    const ledgerLink = document.querySelector('[data-view-audit-ledger]') as HTMLAnchorElement;
    expect(ledgerLink).toBeTruthy();
    ledgerLink.focus();
    await user.keyboard('{Enter}');
    await waitFor(() => expect(router.state.location.pathname).toBe('/app/audit'));
  });

  it('1280px desktop layout renders command center', async () => {
    setDesktopViewport1280();
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    expect(document.querySelector('[data-command-center-page]')).toBeTruthy();
    resetViewport();
  });

  it('focus order places header before proof surface', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    const header = document.querySelector('[data-command-center-header]');
    const proof = document.querySelector('[data-proof-surface-band]');
    expect(header).toBeTruthy();
    expect(proof).toBeTruthy();
    expect(header!.compareDocumentPosition(proof!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('content rail stacks supervisory sections with page rhythm gap', async () => {
    seedShellAuth();
    setDesktopViewport1440();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();

    const pageCss = readFileSync(
      join(process.cwd(), 'src', 'components', 'commandCenter', 'CommandCenterPage', 'CommandCenterPage.module.css'),
      'utf8',
    );
    expect(pageCss).toMatch(/\.contentRail[\s\S]*gap:\s*var\(--spacing-24\)/);

    const summary = document.querySelector('[data-trust-state-summary-row]') as HTMLElement;
    const proofBand = document.querySelector('[data-proof-surface-band]') as HTMLElement;
    expect(summary).toBeTruthy();
    expect(proofBand).toBeTruthy();

    const summaryRect = summary.getBoundingClientRect();
    const proofRect = proofBand.getBoundingClientRect();
    if (summaryRect.bottom > 0 && proofRect.top > 0) {
      const sectionGap = proofRect.top - summaryRect.bottom;
      expect(sectionGap).toBeGreaterThanOrEqual(12);
      expect(sectionGap).toBeLessThanOrEqual(32);
    }

    resetViewport();
  });

  it('trend and channel table use supervisory grid with enforced panel minimums', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    expect(document.querySelector('[data-grid-trend-table]')).toBeTruthy();
    const css = readFileSync(
      join(process.cwd(), 'src', 'components', 'commandCenter', 'CommandCenterPage', 'CommandCenterPage.module.css'),
      'utf8',
    );
    const substrate = readFileSync(join(process.cwd(), 'src', 'styles', 'responsiveGrid.module.css'), 'utf8');
    expect(css).toMatch(/\.proofSurfaceTopRow[\s\S]*composes:\s*supervisoryGrid/);
    expect(substrate).toMatch(
      /minmax\(var\(--sk-grid-trend-panel-min-width\),\s*var\(--sk-grid-supervisory-trend-column\)\)[\s\S]*minmax\(var\(--sk-grid-activity-tile-min-width\),\s*var\(--sk-grid-supervisory-activity-column\)/,
    );
  });

  it('proof surface band stacks supervisory and dual rows with aligned columns', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();

    expect(document.querySelector('[data-proof-surface-band]')).toBeTruthy();
    expect(document.querySelector('[data-recent-envelopes-band]')).toBeTruthy();
    expect(document.querySelector('[data-channel-trust-band]')).toBeTruthy();
    expect(document.querySelector('[data-grid-dual-panel]')).toBeTruthy();

    const pageCss = readFileSync(
      join(process.cwd(), 'src', 'components', 'commandCenter', 'CommandCenterPage', 'CommandCenterPage.module.css'),
      'utf8',
    );
    const substrate = readFileSync(join(process.cwd(), 'src', 'styles', 'responsiveGrid.module.css'), 'utf8');

    expect(pageCss).toMatch(/\.proofSurfaceBand[\s\S]*gap:\s*var\(--sk-space-8\)/);
    expect(pageCss).toMatch(/\.proofEnvelopesSlot[\s\S]*grid-column:\s*1 \/ -1/);
    expect(pageCss).toMatch(/\.proofChannelSlot[\s\S]*grid-column:\s*1 \/ -1/);
    expect(pageCss).toMatch(/\.proofSurfaceTopRow[\s\S]*composes:\s*supervisoryGrid/);
    expect(substrate).toMatch(
      /minmax\(var\(--sk-grid-trend-panel-min-width\),\s*var\(--sk-grid-supervisory-trend-column\)\)[\s\S]*minmax\(var\(--sk-grid-activity-tile-min-width\),\s*var\(--sk-grid-supervisory-activity-column\)/,
    );

    const trend = document.querySelector('[data-verified-revenue-trend]');
    const channel = document.querySelector('[data-channel-trust-table]');
    const envelopesBand = document.querySelector('[data-recent-envelopes-band]');
    const channelBand = document.querySelector('[data-channel-trust-band]');
    const audit = document.querySelector('[data-audit-activity-strip]');
    expect(trend).toBeTruthy();
    expect(channel).toBeTruthy();
    expect(envelopesBand).toBeTruthy();
    expect(channelBand).toBeTruthy();
    expect(audit).toBeTruthy();

    const trendRect = trend!.getBoundingClientRect();
    const channelRect = channel!.getBoundingClientRect();
    const envelopesBandRect = envelopesBand!.getBoundingClientRect();
    const channelBandRect = channelBand!.getBoundingClientRect();
    const auditRect = audit!.getBoundingClientRect();

    expect(Math.abs(trendRect.left - envelopesBandRect.left)).toBeLessThanOrEqual(2);
    expect(Math.abs(channelBandRect.left - envelopesBandRect.left)).toBeLessThanOrEqual(2);
    if (channelBandRect.width > 0 && envelopesBandRect.width > 0) {
      expect(Math.abs(channelBandRect.width - envelopesBandRect.width)).toBeLessThanOrEqual(4);
    }
    if (auditRect.top > 0 && channelRect.top > 0) {
      expect(auditRect.top).toBeLessThan(channelRect.top);
    }
  });

  it('supervisory trend and audit cards share stretch height with expanded chart plot', async () => {
    seedShellAuth();
    setDesktopViewport1440();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();

    const densityCss = readFileSync(join(process.cwd(), 'src', 'tokens', 'density.css'), 'utf8');
    expect(densityCss).toMatch(/--sk-dimension-verified-revenue-chart-height:\s*240px/);
    expect(densityCss).toMatch(/--sk-dimension-command-center-supervisory-row-min-height:\s*360px/);

    const subCss = readFileSync(
      join(process.cwd(), 'src', 'components', 'commandCenter', 'CommandCenterPage', 'CommandCenterSubcomponents.module.css'),
      'utf8',
    );
    expect(subCss).toMatch(/\.chartPlotRegion[\s\S]*flex:\s*1 1 auto/);
    expect(subCss).toMatch(/\.chartPlotRegion[\s\S]*min-height:\s*var\(--sk-dimension-verified-revenue-chart-height\)/);
    expect(subCss).toMatch(/\.chartPlotRegion > \*[\s\S]*height:\s*100%/);
    expect(subCss).toMatch(/\.auditActivityCard[\s\S]*min-height:\s*var\(--sk-grid-supervisory-panel-min-height\)/);
    expect(subCss).toMatch(/\.auditActivityTable[\s\S]*table-layout:\s*fixed/);

    const trend = document.querySelector('[data-verified-revenue-trend]') as HTMLElement;
    const audit = document.querySelector('[data-audit-activity-strip]') as HTMLElement;
    expect(trend).toBeTruthy();
    expect(audit).toBeTruthy();

    const trendRect = trend.getBoundingClientRect();
    const auditRect = audit.getBoundingClientRect();
    if (trendRect.height > 0 && auditRect.height > 0) {
      expect(auditRect.height).toBeLessThanOrEqual(trendRect.height + 4);
    }
    if (trendRect.width > 0 && auditRect.width > 0) {
      expect(trendRect.width).toBeGreaterThan(auditRect.width);
      const trendShare = trendRect.width / (trendRect.width + auditRect.width);
      expect(trendShare).toBeGreaterThan(0.52);
      expect(trendShare).toBeLessThan(0.62);
    }

    resetViewport();
  });

  it('verified revenue trend and channel snapshot use target supervisory scale', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    const tokens = readFileSync(join(process.cwd(), 'src', 'tokens', 'tokens.css'), 'utf8');
    expect(tokens).toMatch(/--sk-dimension-verified-revenue-chart-height:/);
    expect(tokens).not.toMatch(/--sk-dimension-command-center-channel-min-width/);
    const pageCss = readFileSync(
      join(process.cwd(), 'src', 'components', 'commandCenter', 'CommandCenterPage', 'CommandCenterPage.module.css'),
      'utf8',
    );
    expect(pageCss).toMatch(/composes:\s*supervisoryGrid/);
    const subCss = readFileSync(
      join(process.cwd(), 'src', 'components', 'commandCenter', 'CommandCenterPage', 'CommandCenterSubcomponents.module.css'),
      'utf8',
    );
    expect(subCss).toMatch(/\.tableCard[\s\S]*height:\s*100%/);
    expect(subCss).toMatch(/\.chartCard[\s\S]*height:\s*100%/);
    expect(subCss).toMatch(/\.channelTableWrap[\s\S]*flex:\s*1/);
    expect(subCss).toMatch(/\.channelTable[\s\S]*height:\s*100%/);
    expect(subCss).toMatch(/\.channelTable tbody tr[\s\S]*var\(--sk-dimension-channel-trust-snapshot-row-count\)/);
    expect(tokens).toMatch(/--sk-dimension-channel-trust-snapshot-row-count:\s*5/);
    expect(tokens).toMatch(/--sk-dimension-channel-trust-thead-block:/);
    expect(tokens).toMatch(/--sk-dimension-channel-trust-logo-size:\s*1\.4em/);
    expect(tokens).toMatch(/--sk-dimension-command-center-supervisory-row-min-height:/);
    expect(pageCss).toMatch(/composes:\s*supervisoryGrid/);
    const substrate = readFileSync(join(process.cwd(), 'src', 'styles', 'responsiveGrid.module.css'), 'utf8');
    expect(substrate).toMatch(
      /\.supervisoryGrid[\s\S]*min-height:\s*var\(--sk-dimension-command-center-supervisory-row-min-height\)/,
    );
  });

  it('recent trust envelopes table has no horizontal scroll in aligned supervisory column', async () => {
    seedShellAuth();
    setDesktopViewport1440();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();

    const css = readFileSync(
      join(process.cwd(), 'src', 'components', 'commandCenter', 'CommandCenterPage', 'CommandCenterSubcomponents.module.css'),
      'utf8',
    );
    expect(css).toMatch(/\.envelopeTableWrap[\s\S]*overflow-x:\s*visible/);
    expect(css).not.toMatch(/\.envelopeTable[\s\S]*min-width:\s*36rem/);

    const band = document.querySelector('[data-recent-envelopes-band]') as HTMLElement;
    const section = document.querySelector('[data-recent-trust-envelopes]') as HTMLElement;
    const wrap = document.querySelector('[data-envelope-table-scroll-wrap]') as HTMLElement;
    const table = section?.querySelector('table') as HTMLElement;
    expect(band).toBeTruthy();
    expect(section).toBeTruthy();
    expect(wrap).toBeTruthy();
    expect(table).toBeTruthy();

    expect(band.scrollWidth).toBeLessThanOrEqual(band.clientWidth + 2);
    expect(section.scrollWidth).toBeLessThanOrEqual(section.clientWidth + 2);
    expect(wrap.scrollWidth).toBeLessThanOrEqual(wrap.clientWidth + 2);
    expect(table.scrollWidth).toBeLessThanOrEqual(wrap.clientWidth + 2);

    const pageCss = readFileSync(
      join(process.cwd(), 'src', 'components', 'commandCenter', 'CommandCenterPage', 'CommandCenterPage.module.css'),
      'utf8',
    );
    expect(pageCss).toMatch(/\.proofEnvelopesSlot[\s\S]*grid-column:\s*1 \/ -1/);

    const trend = document.querySelector('[data-verified-revenue-trend]') as HTMLElement;
    const channel = document.querySelector('[data-channel-trust-table]') as HTMLElement;
    const bandRect = band.getBoundingClientRect();
    const trendRect = trend.getBoundingClientRect();
    const channelRect = channel.getBoundingClientRect();
    if (bandRect.width > 0 && trendRect.width > 0) {
      expect(Math.abs(trendRect.left - bandRect.left)).toBeLessThanOrEqual(2);
      expect(Math.abs(channelRect.right - bandRect.right)).toBeLessThanOrEqual(4);
      expect(bandRect.width).toBeGreaterThan(trendRect.width + 100);
    }

    const rows = section.querySelectorAll('tbody tr');
    expect(rows.length).toBeGreaterThanOrEqual(4);
    expect(rows.length).toBeLessThanOrEqual(5);
    if (rows.length > 0) {
      expect(document.querySelector('[data-recent-envelope-table-pager]')).toBeTruthy();
    }

    const authorityPill = section.querySelector('[data-trust-chip]') as HTMLElement | null;
    if (authorityPill) {
      const cell = authorityPill.closest('td') as HTMLElement;
      expect(authorityPill.scrollWidth).toBeLessThanOrEqual(cell.clientWidth + 1);
    }

    resetViewport();
  });

  it('channel table has no horizontal scroll and fits at wide desktop', async () => {
    seedShellAuth();
    setDesktopViewport1440();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    const css = readFileSync(
      join(process.cwd(), 'src', 'components', 'commandCenter', 'CommandCenterPage', 'CommandCenterSubcomponents.module.css'),
      'utf8',
    );
    expect(css).toMatch(/\.channelTable[\s\S]*:not\(:last-child\)[\s\S]*border-right/);
    expect(css).toMatch(/\.channelTableWrap[\s\S]*overflow-x:\s*visible/);

    const wrap = document.querySelector('[data-channel-table-scroll-wrap]') as HTMLElement;
    const channelBand = document.querySelector('[data-channel-trust-band]') as HTMLElement;
    const envelopesBand = document.querySelector('[data-recent-envelopes-band]') as HTMLElement;
    expect(wrap).toBeTruthy();
    expect(channelBand).toBeTruthy();
    expect(envelopesBand).toBeTruthy();
    expect(wrap.scrollWidth).toBeLessThanOrEqual(wrap.clientWidth + 2);

    const pageCss = readFileSync(
      join(process.cwd(), 'src', 'components', 'commandCenter', 'CommandCenterPage', 'CommandCenterPage.module.css'),
      'utf8',
    );
    expect(pageCss).toMatch(/\.proofChannelSlot[\s\S]*grid-column:\s*1 \/ -1/);

    if (channelBand.clientWidth > 0 && envelopesBand.clientWidth > 0) {
      expect(Math.abs(channelBand.clientWidth - envelopesBand.clientWidth)).toBeLessThanOrEqual(4);
    }

    const dividerCells = document.querySelectorAll(
      '[data-channel-trust-table] th:not(:last-child), [data-channel-trust-table] td:not(:last-child)',
    );
    expect(dividerCells.length).toBeGreaterThan(0);

    const pillSelectors = [
      '[data-channel-trust-discrepancy-tier="amber"]',
      '[data-channel-trust-row="ch_meta_ads"] [data-status-text]',
      '[data-channel-trust-row="ch_linkedin"] [data-status-text]',
    ];
    for (const selector of pillSelectors) {
      const pill = document.querySelector(selector) as HTMLElement | null;
      expect(pill).toBeTruthy();
      expect(pill!.scrollWidth).toBeLessThanOrEqual(pill!.clientWidth + 1);
    }

    const linkedinRow = document.querySelector('[data-channel-trust-row="ch_linkedin"]') as HTMLElement;
    expect(linkedinRow?.querySelector('[data-evidence-class-badge]')).toBeNull();
    resetViewport();
  });

  it('channel trust snapshot renders exactly five rows with platform logos and no shield icons', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    const rows = document.querySelectorAll('[data-channel-trust-row]');
    expect(rows.length).toBe(5);
    const expectedLogos: Record<string, string> = {
      ch_google_ads: 'google_ads',
      ch_meta_ads: 'meta_ads',
      ch_linkedin: 'linkedin_ads',
      ch_tiktok_ads: 'tiktok_ads',
      ch_organic_search: 'organic_search',
    };
    for (const row of rows) {
      const channelId = row.getAttribute('data-channel-trust-row');
      expect(channelId).toBeTruthy();
      const logo = row.querySelector(`[data-channel-logo="${expectedLogos[channelId!]}"]`) as HTMLElement | null;
      expect(logo).toBeTruthy();
      expect(logo?.getAttribute('data-channel-logo-placeholder')).toBeNull();
      const nameLink = row.querySelector('[data-channel-reconstruction-link]') as HTMLElement | null;
      expect(nameLink).toBeTruthy();
      if (logo && nameLink && logo.offsetHeight > 0 && nameLink.offsetHeight > 0) {
        expect(logo.offsetHeight).toBeGreaterThan(nameLink.offsetHeight);
      }
      expect(row.querySelector('svg')).toBeNull();
      expect(row.querySelector('[data-revenue-reliability]')).toBeTruthy();
    }
  });

  it('channel verified revenue cells omit deterministic authority badges', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    const table = document.querySelector('[data-channel-trust-table]');
    expect(table?.querySelectorAll('[data-verified-revenue-minor]').length).toBe(5);
    const verifiedCells = table?.querySelectorAll('[data-verified-revenue-minor]');
    for (const cell of verifiedCells ?? []) {
      expect(cell.parentElement?.querySelector('[data-trust-chip]')).toBeNull();
      expect(cell.closest('td')?.textContent?.trim().toLowerCase()).not.toMatch(/^deterministic/);
    }
  });

  it('channel trust snapshot renders revenue reliability badges with semantic labels', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    const table = document.querySelector('[data-channel-trust-table]');
    expect(table?.querySelectorAll('[data-revenue-reliability]').length).toBe(5);
    expect(table?.querySelectorAll('[data-trust-chip]').length).toBe(5);
    expect(table?.querySelectorAll('[data-status-text]').length).toBeGreaterThan(0);
    expect(table?.querySelector('[data-channel-trust-discrepancy-tier]')).toBeTruthy();
    const badges = table?.querySelectorAll('[data-revenue-reliability]') ?? [];
    for (const badge of badges) {
      expect(badge.textContent?.toLowerCase()).toMatch(/robust|mixed|fragile/);
    }
  });

  it('channel trust snapshot exposes five CRHAID columns without Channel header', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    expect(screen.getByRole('columnheader', { name: /Revenue Reliability/i })).toBeInTheDocument();
    const headers = Array.from(
      document.querySelectorAll('[data-channel-trust-table] thead th'),
    )
      .filter((th) => !th.querySelector('[data-revenue-reliability-column-header]'))
      .map((th) => th.textContent?.trim());
    expect(headers).toEqual([
      'Claim source (platform)',
      'Verified revenue',
      'Discrepancy rate',
      'Policy authority',
    ]);
    expect(headers.some((h) => h === 'Channel')).toBe(false);
    expect(document.querySelector('[data-channel-trust-group-by]')).toBeTruthy();
  });

  it('claimed revenue column is removed from channel trust snapshot', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    expect(document.querySelector('[data-channel-trust-table] [data-platform-claim-label]')).toBeFalsy();
    expect(screen.queryByRole('columnheader', { name: /Claimed revenue/i })).not.toBeInTheDocument();
    const trustChipCss = readFileSync(join(process.cwd(), 'src', 'styles', 'trustChip.module.css'), 'utf8');
    const statusCss = readFileSync(
      join(process.cwd(), 'src', 'components', 'commandCenter', 'StatusBadges', 'StatusBadges.module.css'),
      'utf8',
    );
    const policyCss = readFileSync(
      join(process.cwd(), 'src', 'components', 'trust', 'PolicyAuthorityPill', 'PolicyAuthorityPill.module.css'),
      'utf8',
    );
    const benchmarkBadgesTs = readFileSync(
      join(process.cwd(), 'src', 'components', 'benchmarks', 'BenchmarkBadges', 'BenchmarkBadges.tsx'),
      'utf8',
    );
    expect(trustChipCss).toMatch(/\.table[\s\S]*--sk-font-size-micro/);
    expect(trustChipCss).toMatch(/\.table[\s\S]*--sk-radius-channel-trust-badge/);
    expect(statusCss).toMatch(/composes: table from/);
    expect(policyCss).not.toMatch(/\.pill\.tableSize/);
    expect(benchmarkBadgesTs).toMatch(/TrustChip/);
    const authorityTs = readFileSync(
      join(process.cwd(), 'src', 'components', 'trust', 'AuthorityBadge', 'AuthorityBadge.tsx'),
      'utf8',
    );
    expect(authorityTs).toMatch(/trustChipClassNames/);
    const channelCard = readFileSync(
      join(process.cwd(), 'src', 'components', 'commandCenter', 'CommandCenterPage', 'ChannelTrustTableCells.tsx'),
      'utf8',
    );
    expect(channelCard).not.toMatch(/PlatformClaimLabel/);
    expect(channelCard).toMatch(/variant="text"/);
  });

  it('command center supervisory chips share compact design without shield icons', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    const statusChips = document.querySelectorAll(
      '[data-trust-state-summary-row] [role="status"], [data-verified-revenue-trend] [role="status"], [data-priority-queue-modal] [role="status"], [data-channel-trust-table] [role="status"], [data-recent-trust-envelopes] [role="status"]',
    );
    expect(statusChips.length).toBeGreaterThan(0);
    for (const chip of statusChips) {
      expect(chip.querySelector('svg')).toBeNull();
    }
    expect(
      document.querySelector('[data-summary-metric="verified_revenue"] [data-trust-chip]')?.textContent?.trim(),
    ).toBe('Deterministic');
    expect(document.querySelector('[data-summary-metric="claims_reconciled"] [data-trust-chip]')).toBeNull();
    expect(document.querySelector('[data-summary-metric="action_authority"] [data-trust-chip]')).toBeNull();
    expect(document.querySelector('[data-summary-metric="open_exceptions"] [data-supervisory-status="alert"]')).toBeNull();
    expect(document.querySelectorAll('[data-trust-state-summary-row] [data-summary-trend="action_authority"]').length).toBe(
      0,
    );
    expect(document.querySelectorAll('[data-trust-state-summary-row] [data-summary-trend="open_exceptions"]').length).toBe(
      0,
    );
    expect(document.querySelectorAll('[data-trust-state-summary-row] button[aria-label*="Source authority"]').length).toBe(
      0,
    );
  });

  it('revenue reliability column uses executive badges with business-oriented labels', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    const copy = readFileSync(join(process.cwd(), 'src', 'commandCenter', 'copy.ts'), 'utf8');
    expect(copy).toMatch(/revenueReliability:\s*'Revenue Reliability'/);
    expect(copy).not.toMatch(/modelAgreement:\s*'Model agreement'/);
    expect(screen.getByRole('columnheader', { name: /Revenue Reliability/i })).toBeInTheDocument();
    const badge = document.querySelector('[data-revenue-reliability]') as HTMLElement | null;
    expect(badge).toBeTruthy();
    expect(badge?.textContent?.toLowerCase()).toMatch(/robust|mixed|fragile/);
    expect(badge?.getAttribute('title')).toMatch(/spend|budget|defensible|assumption/i);
    expect(badge?.getAttribute('title')).not.toMatch(/attribution model/i);
    expect(document.querySelector('[data-revenue-reliability-header-info]')).toBeTruthy();
  });

  it('discrepancy rate column uses color tiers without legacy status badge', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    const css = readFileSync(
      join(
        process.cwd(),
        'src',
        'components',
        'commandCenter',
        'CommandCenterPage',
        'CommandCenterSubcomponents.module.css',
      ),
      'utf8',
    );
    expect(css).toMatch(/\.discrepancyTierGreen/);
    expect(css).toMatch(/\.discrepancyTierAmber/);
    expect(css).toMatch(/\.discrepancyTierRed/);
    expect(css).toMatch(/\.channelIdentity[\s\S]*display:\s*grid/);
    expect(css).toMatch(/\.colAxisCell[\s\S]*text-align:\s*left/);
    const channelCard = readFileSync(
      join(process.cwd(), 'src', 'components', 'commandCenter', 'CommandCenterPage', 'ChannelTrustTableCard.tsx'),
      'utf8',
    );
    expect(channelCard).toMatch(/<colgroup>/);
    const googleRow = document.querySelector('[data-channel-trust-row="ch_google_ads"]');
    expect(googleRow?.textContent).toMatch(/9\.4%/);
    expect(googleRow?.querySelector('[data-channel-trust-discrepancy-tier="amber"]')).toBeTruthy();
    expect(googleRow?.querySelector('[data-discrepancy-badge]')).toBeFalsy();
    const tiktokRow = document.querySelector('[data-channel-trust-row="ch_tiktok_ads"]');
    expect(tiktokRow?.textContent).toContain('$0');
    expect(tiktokRow?.querySelector('[data-channel-trust-discrepancy-tier="unavailable"]')?.textContent).toBe('N/A');
    expect(googleRow?.textContent).toContain('$128,420');
    expect(googleRow?.textContent).not.toMatch(/\$140,560/);
  });
});

describe('Level 10 Harness — Level 9 action-link safety', () => {
  it('does not mount Level 9 execute flows on Command Center', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    expect(document.querySelector('[data-claim-export-flow]')).toBeNull();
    expect(document.querySelector('[data-level9-action]')).toBeNull();
  });
});

describe('Level 10 Harness — mobile and boundedness', () => {
  it('375px layout renders command center', async () => {
    setMobileViewport375();
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    expect(document.querySelector('[data-command-center-page]')).toBeTruthy();
    resetViewport();
  });

  it('priority queue row count bounded', async () => {
    seedShellAuth();
    renderCommandCenter('/app');
    await waitForCommandCenterLoaded();
    expect(document.querySelectorAll('[data-priority-issue]').length).toBeLessThanOrEqual(MAX_PRIORITY_ROWS);
  });
});

describe('Level 10 Harness — sabotage', () => {
  it('source sabotage probes detect violations on bad sample', () => {
    const bad = 'summaryMetrics without AuthorityBadge exportVerifiedReport(path="settings/billing"';
    expect(runLevel10SabotageProbes(bad).filter((p) => p.triggered).length).toBeGreaterThan(0);
  });

  it('clean Command Center source tree does not trigger source sabotage', () => {
    const triggered = runLevel10SourceSabotageProbes().filter((p) => p.triggered);
    expect(triggered).toEqual([]);
  });

  it('clean Command Center page file does not trigger sample sabotage', () => {
    const sample = readFileSync(
      join(process.cwd(), 'src', 'components', 'commandCenter', 'CommandCenterPage', 'CommandCenterPage.tsx'),
      'utf8',
    );
    expect(runLevel10SabotageProbes(sample).filter((p) => p.triggered)).toEqual([]);
  });
});
