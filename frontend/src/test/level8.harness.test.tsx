import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { clearSession, resetAuthStateForTests } from '../auth/sessionStore';
import { runLevel7NegativeScopeScan } from '../audit/level7NegativeScopeScan';
import {
  assertLevel8RoutesExist,
  runLevel8IntegrityProbes,
  runLevel8NegativeScopeScan,
  runLevel8SabotageProbes,
  runLevel8SourceIntegrityProbes,
} from '../audit/level8NegativeScopeScan';
import { runPrivacyScan } from '../audit/privacyScan';
import { runSecretScan } from '../audit/secretScan';
import { AppShellRoutes } from '../app/routes/ShellRoutes';
import {
  createClaimDetailClient,
  resetClaimDetailDelayForTests,
  resetClaimDetailTestMode,
  resetDefaultClaimDetailClient,
  setClaimDetailDelayByIdForTests,
  setClaimDetailDelayForTests,
  setClaimDetailTestMode,
} from '../claims/claimDetailClient';
import { createTrustEnvelopeDetailClient, resetTrustDetailTestMode, setTrustDetailTestMode } from '../trustIndex/trustEnvelopeDetailClient';
import { getDetailRequestCount, resetDetailRequestCounter } from '../detail/requestCounter';
import { resetGovernanceStateForTests } from '../governance/governanceStore';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { Tabs } from '../components/layout/Tabs/Tabs';
import { ExceptionDetailDrawer } from '../components/exceptions/ExceptionDetailModal/ExceptionDetailModal';
import {
  createDetailShellRouter,
  renderDetailRouter,
  renderMountedTrustEnvelopeDrawer,
  resetViewport,
  routerSearch,
  setMobileViewport375,
  seedShellAuth,
} from './level8.helpers';
import { EXCEPTIONS_HARNESS_PATH } from './level9.helpers';

function renderShell(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/app/*" element={<AppShellRoutes />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.useRealTimers();
  resetAuthStateForTests();
  resetGovernanceStateForTests();
  resetDefaultClaimDetailClient();
  resetClaimDetailTestMode();
  resetClaimDetailDelayForTests();
  resetTrustDetailTestMode();
  resetDetailRequestCounter();
  clearSession();
});

describe('Level 8 Harness — Scope and regression', () => {
  it('Level 7 scope scan still passes', () => {
    expect(runLevel7NegativeScopeScan().violations).toEqual([]);
  });

  it('Level 8 scope scan passes', () => {
    expect(runLevel8NegativeScopeScan().violations).toEqual([]);
  });

  it('Level 8 routes and markers exist', () => {
    expect(assertLevel8RoutesExist()).toEqual({ ok: true, missing: [] });
  });

  it('source integrity probes pass', () => {
    expect(runLevel8SourceIntegrityProbes().every((r) => r.ok)).toBe(true);
  });

  it('integrity probes pass on clean tree', () => {
    const results = runLevel8IntegrityProbes();
    expect(results.filter((r) => !r.ok)).toEqual([]);
  });
});

describe('Level 8 Harness — Detail route activation', () => {
  beforeEach(() => {
    resetAuthStateForTests();
    resetGovernanceStateForTests();
    seedShellAuth('owner');
  });

  it.each([
    ['/app/claims/claim_0001', 'data-claim-detail-page', /Meta Ads Claim #0001/i],
    ['/app/channels?expand=ch_paid_search__google_ads', 'data-channels-page', /^Channels$/i],
    ['/app/budget/sim_0001', 'data-budget-detail-page', /Budget simulation sim_0001/i],
  ] as const)('renders %s', async (path, selector, heading) => {
    renderShell(path);
    await waitFor(() => expect(document.querySelector(`[${selector}]`)).toBeInTheDocument());
    await waitFor(() => expect(screen.getAllByText(heading).length).toBeGreaterThan(0));
    expect(document.querySelector('[data-level8-blocked-route]')).not.toBeInTheDocument();
  });

  it('invalid claim id fails closed', async () => {
    renderShell('/app/claims/invalid_id');
    await waitFor(() => expect(document.querySelector('[data-detail-state="not_found"]')).toBeTruthy());
  });
});

describe('Level 8 Harness — Claim detail executive page', () => {
  beforeEach(() => {
    seedShellAuth('owner');
  });

  it('renders single scrollable page without tabs', async () => {
    renderShell('/app/claims/claim_0001');
    await waitFor(() => expect(document.querySelector('[data-claim-detail-loaded]')).toBeTruthy());
    expect(document.querySelector('[data-claim-detail-mode="executive"]')).toBeTruthy();
    expect(document.querySelector('[data-claim-aesthetic="cfo-brief"]')).toBeTruthy();
    expect(screen.queryByRole('tab')).not.toBeInTheDocument();
    expect(document.querySelector('[data-claim-detail-summary]')).toBeTruthy();
    expect(document.querySelector('[data-claim-verdict]')).toBeTruthy();
    expect(document.querySelector('[data-claim-attribution-section]')).toBeTruthy();
    expect(document.querySelector('[data-claim-events-section]')).toBeTruthy();
    expect(document.querySelector('[data-claim-summary-workbench]')).toBeFalsy();
    expect(document.querySelector('[data-claim-tab="evidence"]')).toBeFalsy();
    expect(document.querySelector('[data-incrementality-boundary]')).toBeFalsy();
    expect(screen.queryByRole('button', { name: /View trust record/i })).not.toBeInTheDocument();
    expect(screen.getByText(/Did this ad platform/i)).toBeInTheDocument();
    expect(document.querySelector('[data-detail-return-link]')).toBeFalsy();
  });

  it('shows discrepancy verdict for flagged claim financial delta', async () => {
    renderShell('/app/claims/claim_0004');
    await waitFor(() => expect(document.querySelector('[data-claim-detail-loaded]')).toBeTruthy());
    expect(document.querySelector('[data-claim-verdict="discrepancy"]')).toBeTruthy();
    expect(document.querySelector('[data-summary-metric-value="claim_claimed"]')).toBeTruthy();
    expect(document.querySelector('[data-summary-metric="claim_verified"]')).toBeTruthy();
    expect(document.querySelector('[data-executive-revenue-display]')).toBeTruthy();
    expect(document.querySelector('[data-contextualized-delta-block]')).toBeTruthy();
    expect(document.querySelector('[data-claim-delta-context]')).toBeNull();
    expect(document.querySelector('[data-variance-policy-gate]')).toBeNull();
    expect(document.querySelector('[data-discrepancy-percent]')?.textContent).toMatch(
      /of claimed revenue/,
    );
  });

  it('shows verified verdict for within-tolerance claim_0002', async () => {
    renderShell('/app/claims/claim_0002');
    await waitFor(() => expect(document.querySelector('[data-claim-detail-loaded]')).toBeTruthy());
    expect(document.querySelector('[data-claim-verdict="verified"]')).toBeTruthy();
    expect(screen.getByText(/^Numbers match$/i)).toBeInTheDocument();
  });

  it('renders two-tier attribution breakdown without synthesis aside', async () => {
    renderShell('/app/claims/claim_0004');
    await waitFor(() => expect(document.querySelector('[data-claim-attribution-breakdown]')).toBeTruthy());
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
    expect(document.querySelector('[data-claim-attribution-model]')).toBeTruthy();
    expect(document.querySelector('[data-claim-paid-attribution]')).toBeTruthy();
    expect(document.querySelectorAll('[data-claim-paid-row]').length).toBeGreaterThan(0);
    expect(document.querySelector('[data-claim-journey-origins]')).toBeTruthy();
    expect(document.querySelectorAll('[data-claim-journey-row]').length).toBeGreaterThan(0);
    expect(document.querySelector('[data-claim-attribution-synthesis]')).toBeNull();
    expect(document.querySelector('[data-claim-attribution-chart]')).toBeFalsy();
    expect(document.querySelector('[data-claim-money-strip]')).toBeTruthy();
    expect(document.querySelector('[data-claim-paid-channel-link]')?.getAttribute('href')).toMatch(
      /^\/app\/channels\?expand=ch_/,
    );
  });

  it('renders matched and unmatched claim events', async () => {
    renderShell('/app/claims/claim_0001');
    await waitFor(() => expect(document.querySelector('[data-claim-events-section]')).toBeTruthy());
    expect(document.querySelectorAll('[data-claim-event-row]').length).toBeGreaterThan(0);
    expect(document.querySelector('[data-claim-event-match="unmatched"]')).toBeTruthy();
  });

  it('unverified claim shows one sentence and exclude button', async () => {
    const user = userEvent.setup();
    renderShell('/app/claims/claim_0011');
    await waitFor(() => expect(document.querySelector('[data-claim-unverified-panel]')).toBeTruthy());
    expect(document.querySelector('[data-claim-detail-mode="unverified"]')).toBeTruthy();
    expect(document.querySelector('[data-claim-unverified-message]')?.textContent).toMatch(
      /Unverified Claim: No matching commerce receipt found/i,
    );
    expect(document.querySelector('[data-claim-detail-summary]')).toBeFalsy();
    const exclude = screen.getByRole('button', { name: /Exclude from Budget Simulator/i });
    await user.click(exclude);
    await waitFor(() =>
      expect(document.querySelector('[data-claim-exclude-status="success"]')).toBeTruthy(),
    );
  });
});

describe('Level 8 Harness — Trust envelope operator drawer', () => {
  beforeEach(() => seedShellAuth('owner'));

  it('mounted trust envelope drawer opens operator view without /trust/* route', async () => {
    renderMountedTrustEnvelopeDrawer('env_0001');
    await waitFor(() => expect(document.querySelector('[data-claim-trust-envelope-drawer]')).toBeTruthy());
    expect(document.querySelector('[data-trust-envelope-operator-view]')).toBeTruthy();
    expect(document.querySelector('[data-trust-json-column]')).toBeFalsy();
  });

  it('deterministic truth panel exposes hero revenue in drawer', async () => {
    renderMountedTrustEnvelopeDrawer('env_0001');
    await waitFor(() => expect(document.querySelector('[data-claim-trust-envelope-drawer]')).toBeTruthy());
    expect(screen.getByRole('heading', { name: /B\. Deterministic Truth/i })).toBeInTheDocument();
    expect(document.querySelector('[data-trust-envelope-verified-revenue]')?.textContent).toBe('$482,316.84');
  });

  it('attribution model panel exposes lettered title in drawer', async () => {
    renderMountedTrustEnvelopeDrawer('env_0001');
    await waitFor(() => expect(document.querySelector('[data-claim-trust-envelope-drawer]')).toBeTruthy());
    expect(screen.getByRole('heading', { name: /C\. Attribution Model/i })).toBeInTheDocument();
  });

  it('confidence metadata panel exposes lettered title in drawer', async () => {
    renderMountedTrustEnvelopeDrawer('env_0001');
    await waitFor(() => expect(document.querySelector('[data-claim-trust-envelope-drawer]')).toBeTruthy());
    expect(screen.getByRole('heading', { name: /D\. Confidence Metadata/i })).toBeInTheDocument();
  });

  it('benchmark metadata folds inside confidence panel in drawer', async () => {
    renderMountedTrustEnvelopeDrawer('env_0001');
    await waitFor(() => expect(document.querySelector('[data-claim-trust-envelope-drawer]')).toBeTruthy());
    expect(screen.getByRole('heading', { name: /D\. Confidence Metadata/i })).toBeInTheDocument();
    expect(document.querySelector('[data-trust-envelope-benchmark-fold]')).toBeTruthy();
    expect(screen.queryByRole('heading', { name: /E\. Benchmark Metadata/i })).not.toBeInTheDocument();
  });

  it('policy authority panel exposes lettered title in drawer', async () => {
    renderMountedTrustEnvelopeDrawer('env_0001');
    await waitFor(() => expect(document.querySelector('[data-claim-trust-envelope-drawer]')).toBeTruthy());
    expect(screen.getByRole('heading', { name: /F\. Policy Authority/i })).toBeInTheDocument();
  });

  it('audit panel exposes audit reference link without forensic hashes', async () => {
    renderMountedTrustEnvelopeDrawer('env_0001');
    await waitFor(() => expect(document.querySelector('[data-claim-trust-envelope-drawer]')).toBeTruthy());
    expect(screen.getByRole('heading', { name: /Audit record/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /AUD-2026-07-02-004182/i })).toBeInTheDocument();
  });

  it('inline export report button renders without verify signature affordance', async () => {
    renderMountedTrustEnvelopeDrawer('env_0001');
    await waitFor(() => expect(document.querySelector('[data-claim-trust-envelope-drawer]')).toBeTruthy());
    const drawer = document.querySelector('[data-claim-trust-envelope-drawer]') as HTMLElement;
    expect(within(drawer).getByRole('button', { name: /Export report/i })).toBeInTheDocument();
    expect(within(drawer).queryByRole('button', { name: /Verify signature/i })).not.toBeInTheDocument();
  });

  it('operator view exposes auditReference without forensic fields', async () => {
    resetTrustDetailTestMode();
    const outcome = await createTrustEnvelopeDetailClient().getTrustEnvelopeDetail(
      'tenant_test_001',
      'env_0001',
    );
    if (outcome.kind !== 'loaded') throw new Error('expected loaded trust envelope detail');
    expect(outcome.detail.auditReference).toBe('AUD-2026-07-02-004182');
    expect('jsonContract' in outcome.detail).toBe(false);
    expect('provenanceChain' in outcome.detail).toBe(false);
    expect('auditSignature' in outcome.detail).toBe(false);
  });
});

describe('Level 8 Harness — Channel inline expansion (CDO remediation)', () => {
  beforeEach(() => seedShellAuth('owner'));

  it('renders executive financial defense expansion without analyst/API surfaces', async () => {
    renderShell('/app/channels?expand=ch_paid_search__google_ads');
    await waitFor(() => expect(document.querySelector('[data-channels-page]')).toBeTruthy());
    await waitFor(() =>
      expect(
        document.querySelector('[data-channel-inline-expansion="ch_paid_search__google_ads"]'),
      ).toBeTruthy(),
    );

    expect(document.querySelector('[data-channel-inline-section="revenue"]')).toBeTruthy();
    expect(document.querySelector('[data-channel-inline-verified]')).toBeTruthy();
    expect(document.querySelector('[data-channel-inline-claimed]')).toBeTruthy();
    expect(document.querySelector('[data-channel-inline-difference]')).toBeTruthy();
    expect(document.querySelector('[data-channel-inline-deck="defense"]')).toBeTruthy();
    expect(document.querySelector('[data-channel-inline-campaigns]')).toBeTruthy();
    expect(document.querySelector('[data-channel-inline-trend]')).toBeTruthy();
    expect(document.querySelector('[data-channel-inline-model]')?.textContent).toMatch(
      /Data-driven attribution/i,
    );
    expect(document.querySelector('[data-channel-reliability]')).toBeTruthy();
    expect(document.querySelector('[data-channel-inline-deck="context"]')).toBeTruthy();
    expect(document.querySelector('[data-channel-inline-deck="defense"] .deckLabel')).toBeFalsy();
    expect(screen.queryByText(/^Confidence:/i)).not.toBeInTheDocument();

    // Negative-scope: analyst / API surfaces must be absent
    expect(document.querySelector('[data-channel-model-table]')).toBeFalsy();
    expect(document.querySelector('[data-channel-deck="math-models"]')).toBeFalsy();
    expect(screen.queryByText(/do not prove causal lift/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: /Confidence interval/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: /Related TrustEnvelopes/i })).not.toBeInTheDocument();
    expect(document.querySelector('[data-channel-trust-envelope-expansion]')).toBeFalsy();
    expect(document.querySelector('[data-channel-detail-page]')).toBeFalsy();
  });

  it('legacy detail route redirects into overview expand deep-link', async () => {
    renderShell('/app/channels/ch_paid_search__google_ads');
    await waitFor(() => expect(document.querySelector('[data-channels-page]')).toBeTruthy());
    await waitFor(() =>
      expect(
        document.querySelector('[data-channel-inline-expansion="ch_paid_search__google_ads"]'),
      ).toBeTruthy(),
    );
    expect(document.querySelector('[data-channel-detail-page]')).toBeFalsy();
  });
});

describe('Level 8 Harness — Exception modal', () => {
  beforeEach(() => seedShellAuth('owner'));

  it('opens modal with governed Level 9 exception actions', async () => {
    renderShell(EXCEPTIONS_HARNESS_PATH);
    await waitFor(() => expect(document.querySelector('[data-exceptions-page]')).toBeTruthy());
    await waitFor(() => expect(document.querySelector('[data-exception-detail-trigger]')).toBeTruthy());
    const user = userEvent.setup();
    const trigger = document.querySelector('[data-exception-detail-trigger]') as HTMLButtonElement;
    await user.click(trigger);
    await waitFor(() => expect(document.querySelector('[data-exception-detail-modal]')).toBeTruthy());
    expect(document.querySelector('[data-exception-detail-drawer]')).toBeTruthy();
    expect(document.querySelector('[data-modal-panel]')).toBeTruthy();
    expect(document.querySelector('[data-drawer-panel]')).toBeNull();
    expect(document.querySelector('[data-exception-action-controls]')).toBeTruthy();

    const completeReview = document.querySelector(
      '[data-exception-action-group="complete-review"]',
    ) as HTMLElement;
    const continueInvestigation = document.querySelector(
      '[data-exception-action-group="continue-investigation"]',
    ) as HTMLElement;
    const governedFollowUp = document.querySelector(
      '[data-exception-action-group="governed-follow-up"]',
    ) as HTMLElement;

    expect(completeReview).toBeTruthy();
    expect(continueInvestigation).toBeTruthy();
    expect(governedFollowUp).toBeTruthy();
    expect(completeReview.querySelectorAll('[data-level9-action]')).toHaveLength(1);
    expect(continueInvestigation.querySelectorAll('[data-level9-action]')).toHaveLength(2);
    expect(governedFollowUp.querySelectorAll('[data-level9-action]')).toHaveLength(2);
  });
});

describe('Level 8 Harness — Parent context and deep links', () => {
  beforeEach(() => seedShellAuth('owner'));

  it('return from claim detail preserves ledger query', async () => {
    const ledgerUrl = '/app/claims?claimSource=meta_ads&sort=discrepancy&sortDir=desc';
    const router = createDetailShellRouter([ledgerUrl, '/app/claims/claim_0001'], 1);
    renderDetailRouter(router);
    await waitFor(() => expect(document.querySelector('[data-claim-detail-loaded]')).toBeTruthy());
    await router.navigate(-1);
    await waitFor(() => {
      expect(router.state.location.pathname).toBe('/app/claims');
      expect(routerSearch(router)).toContain('claimSource=meta_ads');
    });
  });

  it('direct deep link does not show ledger return chrome on claim detail', async () => {
    renderShell('/app/claims/claim_0001');
    await waitFor(() => expect(document.querySelector('[data-claim-detail-loaded]')).toBeTruthy());
    expect(document.querySelector('[data-detail-return-link]')).toBeFalsy();
    expect(screen.queryByRole('link', { name: /Return to claims ledger/i })).not.toBeInTheDocument();
  });
});

describe('Level 8 Harness — Detail DTO and bounded requests', () => {
  beforeEach(() => {
    resetDetailRequestCounter();
    seedShellAuth('owner');
  });

  it('claim detail uses bounded request count', async () => {
    await createClaimDetailClient().getClaimDetail('tenant_1', 'claim_0001');
    expect(getDetailRequestCount()).toBeLessThanOrEqual(3);
  });

  it('cross-tenant detail fails closed', async () => {
    setClaimDetailTestMode('cross_tenant');
    const outcome = await createClaimDetailClient().getClaimDetail('tenant_1', 'claim_0001');
    expect(outcome.kind).toBe('scope_denied');
  });
});

describe('Level 8 Harness — Accessibility', () => {
  beforeEach(() => {
    resetViewport();
  });

  it('tabs support arrow keyboard navigation', async () => {
    const user = userEvent.setup();
    render(
      <Tabs
        items={[
          { id: 'a', label: 'Tab A', panel: <div>A</div> },
          { id: 'b', label: 'Tab B', panel: <div>B</div> },
        ]}
      />,
    );
    const tabA = screen.getByRole('tab', { name: 'Tab A' });
    tabA.focus();
    await user.keyboard('{ArrowRight}');
    expect(screen.getByRole('tab', { name: 'Tab B' })).toHaveFocus();
  });

  it('375px claim detail remains usable', async () => {
    try {
      setMobileViewport375();
      seedShellAuth('owner');
      renderShell('/app/claims');
      await waitFor(() => expect(document.querySelector('[data-compact-ledger-row]')).toBeTruthy());
      const user = userEvent.setup();
      await user.click(screen.getAllByRole('link', { name: /Open claim record for claim_/i })[0]);
      await waitFor(() => expect(document.querySelector('[data-claim-detail-loaded]')).toBeTruthy());
    } finally {
      resetViewport();
    }
  });
});

describe('Level 8 Harness — Sabotage controls', () => {
  it('sabotage probes fire on poisoned sample', () => {
    const poisoned =
      'TrustEnvelopeDetailPage TrustEnvelopeJsonViewer provenanceChain verifySignature(); exportVerifiedReport(); Level8BlockedDetailPage RadarChart';
    const triggered = runLevel8SabotageProbes(poisoned).filter((d) => d.triggered);
    expect(triggered.length).toBeGreaterThan(0);
    expect(triggered.map((d) => d.name)).toContain('export-executes');
    expect(triggered.map((d) => d.name)).toContain('trust-detail-route-absent');
  });

  it('clean claim page sample does not trigger sabotage', () => {
    const clean = readFileSync(
      join(process.cwd(), 'src', 'components', 'claims', 'ClaimDetailPage', 'ClaimDetailPage.tsx'),
      'utf8',
    );
    const triggered = runLevel8SabotageProbes(clean).filter((d) => d.triggered);
    expect(triggered).toEqual([]);
  });

  it('clean operator drawer sample does not trigger forensic sabotage', () => {
    const clean = readFileSync(
      join(process.cwd(), 'src', 'components', 'trust', 'TrustEnvelopeOperatorView', 'TrustEnvelopeOperatorDrawer.tsx'),
      'utf8',
    );
    const triggered = runLevel8SabotageProbes(clean).filter((d) => d.triggered);
    expect(triggered).toEqual([]);
  });
});

describe('Level 8 Harness — Privacy scan roots', () => {
  it('privacy and secret scans include Level 8 evidence path when present', () => {
    const privacy = runPrivacyScan();
    const secret = runSecretScan();
    expect(privacy.violations).toEqual([]);
    expect(secret.violations).toEqual([]);
  });
});

describe('Level 8 Harness — Exception modal component', () => {
  it('Escape closes modal via Modal shell', async () => {
    seedShellAuth('owner');
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<ExceptionDetailDrawer exceptionId="exc_0001" open onClose={onClose} />);
    await waitFor(() => expect(document.querySelector('[data-exception-detail-modal]')).toBeTruthy());
    expect(document.querySelector('[data-modal-panel]')).toBeTruthy();
    await user.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalled();
  });
});

describe('Level 8 Harness — Detail state matrix (Iteration II)', () => {
  beforeEach(() => seedShellAuth('owner'));

  const stateCases = [
    ['permission_denied', 'permission_denied', /permission/i],
    ['schema_invalid', 'schema_invalid', /contract validation/i],
    ['stale', 'stale_version', /stale/i],
    ['corrupted', 'corrupted_evidence', /could not be reconstructed/i],
    ['object_id_mismatch', 'object_id_mismatch', /identity does not match/i],
    ['network_error', 'network_error', /network unavailable/i],
  ] as const;

  it.each(stateCases)('claim detail renders %s safely', async (testMode, expectedState, copyPattern) => {
    setClaimDetailTestMode(testMode);
    renderShell('/app/claims/claim_0001');
    await waitFor(() =>
      expect(document.querySelector(`[data-detail-state="${expectedState}"]`)).toBeTruthy(),
    );
    expect(screen.getByText(copyPattern)).toBeInTheDocument();
    expect(screen.queryByText(/Internal Server Error/i)).not.toBeInTheDocument();
    expect(document.querySelector('[data-detail-parent-fallback]')).toBeTruthy();
  });

  it('scope_denied renders on cross-tenant detail', async () => {
    setClaimDetailTestMode('cross_tenant');
    renderShell('/app/claims/claim_0001');
    await waitFor(() =>
      expect(document.querySelector('[data-detail-state="scope_denied"]')).toBeTruthy(),
    );
    expect(screen.getByText(/scope does not permit/i)).toBeInTheDocument();
  });

  it('long_loading shows non-authoritative progress copy', async () => {
    setClaimDetailDelayForTests(2500);
    renderShell('/app/claims/claim_0001');
    await waitFor(() => expect(document.querySelector('[data-detail-state="loading"]')).toBeTruthy());
    await waitFor(() => expect(screen.getByText(/Still loading verified trust state/i)).toBeInTheDocument(), {
      timeout: 3500,
    });
    resetClaimDetailDelayForTests();
  }, 8000);

  it('network_error retry reloads detail', async () => {
    setClaimDetailTestMode('network_error');
    renderShell('/app/claims/claim_0001');
    await waitFor(() =>
      expect(document.querySelector('[data-detail-state="network_error"]')).toBeTruthy(),
    );
    setClaimDetailTestMode('default');
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /Retry/i }));
    await waitFor(() => expect(document.querySelector('[data-claim-detail-loaded]')).toBeTruthy());
  });

  it('trust drawer shows unavailable state for unknown envelope', async () => {
    setTrustDetailTestMode('not_found');
    renderMountedTrustEnvelopeDrawer('env_0001');
    await waitFor(() => expect(document.querySelector('[data-claim-trust-envelope-drawer]')).toBeTruthy());
    await waitFor(() => expect(document.querySelector('[data-detail-state="unavailable"]')).toBeTruthy());
    resetTrustDetailTestMode();
  });
});

describe('Level 8 Harness — Parent context multi-surface (Iteration II)', () => {
  beforeEach(() => seedShellAuth('owner'));

  it('channel overview expand deep-link preserves overview route', async () => {
    const router = createDetailShellRouter(
      ['/app/channels', '/app/channels?expand=ch_paid_search__google_ads'],
      1,
    );
    renderDetailRouter(router);
    await waitFor(() =>
      expect(
        document.querySelector('[data-channel-inline-expansion="ch_paid_search__google_ads"]'),
      ).toBeTruthy(),
    );
    expect(router.state.location.pathname).toBe('/app/channels');
    await router.navigate(-1);
    await waitFor(() => expect(router.state.location.pathname).toBe('/app/channels'));
  });

  it('budget input to detail to back preserves parent route', async () => {
    const router = createDetailShellRouter(['/app/budget', '/app/budget/sim_0001'], 1);
    renderDetailRouter(router);
    await waitFor(() => expect(document.querySelector('[data-budget-detail-loaded]')).toBeTruthy());
    await router.navigate(-1);
    await waitFor(() => expect(router.state.location.pathname).toBe('/app/budget'));
  });
});

describe('Level 8 Harness — Direct deep-link safe return (Iteration II)', () => {
  beforeEach(() => seedShellAuth('owner'));

  it.each([
    ['/app/budget/sim_0001', '/app/budget', /Return to budget simulation/i],
  ] as const)('direct %s uses canonical parent href %s', async (path, href, label) => {
    renderShell(path);
    await waitFor(() => expect(document.querySelector('[data-detail-return-link]')).toBeTruthy());
    expect(screen.getByRole('link', { name: label })).toHaveAttribute('href', href);
  });

  it('legacy channel detail path redirects without return-link shell', async () => {
    renderShell('/app/channels/ch_paid_search__google_ads');
    await waitFor(() => expect(document.querySelector('[data-channels-page]')).toBeTruthy());
    expect(document.querySelector('[data-detail-return-link]')).toBeFalsy();
    expect(
      document.querySelector('[data-channel-inline-expansion="ch_paid_search__google_ads"]'),
    ).toBeTruthy();
  });

  it('claim detail omits ledger return link on loaded executive page', async () => {
    renderShell('/app/claims/claim_0001');
    await waitFor(() => expect(document.querySelector('[data-claim-detail-loaded]')).toBeTruthy());
    expect(document.querySelector('[data-detail-return-link]')).toBeFalsy();
  });

  it('return link navigates to canonical parent without history back', async () => {
    const router = createDetailShellRouter(['/app/budget/sim_0001']);
    renderDetailRouter(router);
    await waitFor(() => expect(document.querySelector('[data-budget-detail-loaded]')).toBeTruthy());
    const user = userEvent.setup();
    await user.click(screen.getByRole('link', { name: /Return to budget simulation/i }));
    await waitFor(() => expect(router.state.location.pathname).toBe('/app/budget'));
  });
});

describe('Level 8 Harness — Exception modal accessibility (Iteration II)', () => {
  beforeEach(() => seedShellAuth('owner'));

  it('focus trap wraps Tab and Shift+Tab; Escape restores invoking row focus', async () => {
    renderShell(EXCEPTIONS_HARNESS_PATH);
    await waitFor(() => expect(document.querySelector('[data-exceptions-page]')).toBeTruthy());
    const user = userEvent.setup();
    const triggers = document.querySelectorAll('[data-exception-detail-trigger]');
    expect(triggers.length).toBeGreaterThan(0);
    const activeTrigger = (triggers[1] ?? triggers[0]) as HTMLButtonElement;
    activeTrigger.focus();
    await user.click(activeTrigger);
    await waitFor(() => expect(document.querySelector('[data-modal-panel]')).toBeTruthy());
    await waitFor(() => expect(document.querySelector('[data-exception-action-controls]')).toBeTruthy());
    const modal = document.querySelector('[data-modal-panel]') as HTMLElement;
    expect(document.querySelector('[data-drawer-panel]')).toBeNull();
    const closeBtn = within(modal).getByRole('button', { name: /Close modal/i });
    // Modal shell focuses the dialog panel on open (PriorityQueue DNA), then trap cycles focusables.
    expect(modal.contains(document.activeElement)).toBe(true);

    const modalButtons = within(modal).getAllByRole('button');
    expect(modalButtons.length).toBeGreaterThan(1);
    const lastBtn = modalButtons[modalButtons.length - 1];
    lastBtn.focus();
    await user.keyboard('{Tab}');
    expect(closeBtn).toHaveFocus();

    closeBtn.focus();
    await user.keyboard('{Shift>}{Tab}{/Shift}');
    expect(lastBtn).toHaveFocus();

    for (let i = 0; i < 12; i++) {
      await user.tab();
      expect(modal.contains(document.activeElement)).toBe(true);
    }

    await user.keyboard('{Escape}');
    await waitFor(() => expect(document.querySelector('[data-modal-panel]')).toBeFalsy());
    expect(activeTrigger).toHaveFocus();
  });
});

describe('Level 8 Harness — Claim detail executive sections (Iteration II)', () => {
  beforeEach(() => seedShellAuth('owner'));

  it('executive sections remain present without tab chrome', async () => {
    renderShell('/app/claims/claim_0001');
    await waitFor(() => expect(document.querySelector('[data-claim-detail-loaded]')).toBeTruthy());
    expect(document.querySelector('[data-claim-attribution-section]')).toBeTruthy();
    expect(document.querySelector('[data-claim-events-section]')).toBeTruthy();
    expect(screen.queryByRole('tab')).not.toBeInTheDocument();
  });
});

describe('Level 8 Harness — Stale detail in-flight (Iteration II)', () => {
  beforeEach(() => seedShellAuth('owner'));

  it('late claim A response cannot overwrite active claim B detail', async () => {
    setClaimDetailDelayByIdForTests({ claim_0001: 900 });
    const router = createDetailShellRouter(['/app/claims/claim_0001']);
    renderDetailRouter(router);
    await router.navigate('/app/claims/claim_0002');
    await waitFor(() => expect(document.querySelector('[data-claim-detail-loaded]')).toBeTruthy());
    expect(screen.getAllByText(/Google Ads Claim #0002/i).length).toBeGreaterThan(0);
    await new Promise((resolve) => setTimeout(resolve, 1000));
    expect(screen.getAllByText(/Google Ads Claim #0002/i).length).toBeGreaterThan(0);
    expect(screen.queryByText(/Meta Ads Claim #0001/i)).not.toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/app/claims/claim_0002');
  });
});

describe('Level 8 Harness — Budget proposal affordance (Iteration II)', () => {
  beforeEach(() => seedShellAuth('owner'));

  it('budget detail exposes governed proposal flow control', async () => {
    renderShell('/app/budget/sim_0001');
    await waitFor(() => expect(document.querySelector('[data-budget-detail-loaded]')).toBeTruthy());
    expect(document.querySelector('[data-budget-proposal-flow]')).toBeTruthy();
    expect(screen.getByRole('button', { name: /Submit proposal/i })).toHaveAttribute('data-level9-action');
  });
});

describe('Level 8 Harness — Mounted boundedness (Iteration II)', () => {
  beforeEach(() => seedShellAuth('owner'));

  it('executive claim page does not increase detail request count on re-render markers', async () => {
    renderShell('/app/claims/claim_0001');
    await waitFor(() => expect(document.querySelector('[data-claim-detail-loaded]')).toBeTruthy());
    const afterLoad = getDetailRequestCount();
    expect(document.querySelector('[data-claim-attribution-section]')).toBeTruthy();
    expect(document.querySelector('[data-claim-events-section]')).toBeTruthy();
    expect(getDetailRequestCount()).toBe(afterLoad);
  });

  it('channel expansion campaign list stays bounded', async () => {
    renderShell('/app/channels?expand=ch_paid_search__google_ads');
    await waitFor(() =>
      expect(
        document.querySelector('[data-channel-inline-expansion="ch_paid_search__google_ads"]'),
      ).toBeTruthy(),
    );
    const campaigns = document.querySelectorAll('[data-channel-campaign-row]');
    expect(campaigns.length).toBeGreaterThan(0);
    expect(campaigns.length).toBeLessThanOrEqual(25);
  });
});

describe('Level 8 Harness — 375px multi-surface (Iteration II)', () => {
  beforeEach(() => {
    resetViewport();
    seedShellAuth('owner');
  });

  it.each([
    ['/app/claims/claim_0001', 'data-claim-detail-loaded'],
    ['/app/channels?expand=ch_paid_search__google_ads', 'data-channel-inline-expansion'],
    ['/app/budget/sim_0001', 'data-budget-detail-loaded'],
  ] as const)('375px %s remains usable', async (path, marker) => {
    try {
      setMobileViewport375();
      renderShell(path);
      await waitFor(() => expect(document.querySelector(`[${marker}]`)).toBeTruthy());
    } finally {
      resetViewport();
    }
  });

  it('375px exception modal opens with governed actions', async () => {
    try {
      setMobileViewport375();
      renderShell(EXCEPTIONS_HARNESS_PATH);
      await waitFor(() => expect(document.querySelector('[data-exceptions-page]')).toBeTruthy());
      await waitFor(() => expect(document.querySelector('[data-exception-detail-trigger]')).toBeTruthy());
      const user = userEvent.setup();
      const trigger = document.querySelector('[data-exception-detail-trigger]') as HTMLButtonElement;
      await user.click(trigger);
      await waitFor(() => expect(document.querySelector('[data-exception-detail-modal]')).toBeTruthy());
      expect(document.querySelector('[data-modal-panel]')).toBeTruthy();
      expect(document.querySelector('[data-exception-action-controls]')).toBeTruthy();
    } finally {
      resetViewport();
    }
  });
});