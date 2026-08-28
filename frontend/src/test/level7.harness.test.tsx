import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createMockSession, createMockTenant } from '../auth/authClient';
import { resolveSafeRedirect, LEVEL7_PERMITTED_ROUTES, LEVEL8_PLUS_BLOCKED_ROUTES } from '../auth/redirectGuard';
import { clearSession, establishTenant, resetAuthStateForTests, setBootstrapReady } from '../auth/sessionStore';
import { runLevel1NegativeScopeScan } from '../audit/level1NegativeScopeScan';
import { runLevel2NegativeScopeScan } from '../audit/level2NegativeScopeScan';
import { runLevel3NegativeScopeScan } from '../audit/level3NegativeScopeScan';
import { runLevel4NegativeScopeScan } from '../audit/level4NegativeScopeScan';
import { runLevel5NegativeScopeScan } from '../audit/level5NegativeScopeScan';
import { runLevel6NegativeScopeScan } from '../audit/level6NegativeScopeScan';
import {
  assertLevel7RoutesExist,
  runLevel7IntegrityProbes,
  runLevel7NegativeScopeScan,
  runLevel7SabotageProbes,
  runLevel7SourceIntegrityProbes,
} from '../audit/level7NegativeScopeScan';
import { runNegativeScopeScan } from '../audit/negativeScopeScan';
import { runPrivacyScan } from '../audit/privacyScan';
import { runSecretScan } from '../audit/secretScan';
import { runTokenAudit } from '../audit/tokenAudit';
import { runFinancialScan } from '../audit/financialScan';
import { AppShellRoutes } from '../app/routes/ShellRoutes';
import {
  createClaimsLedgerClient,
  resetDefaultClaimsLedgerClient,
  setDefaultClaimsLedgerClient,
  setSyntheticClaimsDataset,
  resetSyntheticClaimsDataset,
  baseClaimRow,
  setClaimsListDelayForTests,
  setClaimsListDelayBySourceForTests,
  resetClaimsListDelayForTests,
} from '../claims/claimsClient';
import {
  claimsCampaignClassFilter,
  claimsClaimSourceFilter,
  claimsCommerceRailFilter,
  claimsFilterComboboxes,
  claimsSortFilter,
  claimsVerificationStatusFilter,
  createClaimsShellRouter,
  renderClaimsRouter,
  resetViewport,
  routerSearch,
  setMobileViewport375,
  waitForClaimsTableRows,
} from './level7.helpers';
import { getLedgerRequestCount, resetLedgerRequestCounter } from '../ledger/requestCounter';
import { validateListDtoBoundary, FORBIDDEN_LIST_ENVELOPE_FIELDS } from '../ledger/listDtoValidation';
import { executeServerQuery, createSyntheticDataset } from '../ledger/queryEngine';
import { parseCanonicalClaimsQuery } from '../ledger/claimsQueryState';
import { MAX_DOM_TABLE_ROWS } from '../operationalAudit/pagination';
import { resetGovernanceStateForTests, setCurrentUserRole } from '../governance/governanceStore';
import { canViewClaims } from '../ledger/permissions';
import { getTableDomRowCount } from './level5.helpers';
import { ClaimsLedgerTable } from '../components/claims/ClaimsLedgerTable/ClaimsLedgerTable';
import { ConfidenceCell } from '../components/ledger/ConfidenceCell/ConfidenceCell';
import { BenchmarkCell } from '../components/ledger/BenchmarkCell/BenchmarkCell';
import { CompactLedgerRow } from '../components/ledger/CompactLedgerRow/CompactLedgerRow';
import { createTrustIndexClient, setSyntheticTrustIndexDataset, resetDefaultTrustIndexClient } from '../trustIndex/trustIndexClient';
import {
  buildAuditReferenceHref,
  buildTrustEnvelopeAuditReferenceHref,
} from '../detail/auditReference';
import { resetDefaultOperationalAuditClient } from '../operationalAudit/operationalAuditClient';
import { createBenchmarksClient, setSyntheticBenchmarksDataset } from '../benchmarks/benchmarksClient';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import type { ClaimLedgerRowDTO } from '../ledger/types';

function renderShell(initialPath = '/app/claims') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/app/*" element={<AppShellRoutes />} />
        <Route path="/login" element={<div>Login page</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

function seedShellAuth(role: 'owner' | 'viewer' | 'billing_only' = 'owner') {
  establishTenant(createMockSession(), createMockTenant());
  setBootstrapReady();
  setCurrentUserRole(role);
  resetDefaultClaimsLedgerClient();
  resetDefaultTrustIndexClient();
  resetDefaultOperationalAuditClient();
  setDefaultClaimsLedgerClient(createClaimsLedgerClient());
}

describe('Level 7 Harness — Scope and regression', () => {
  beforeEach(() => {
    resetAuthStateForTests();
    resetGovernanceStateForTests();
    resetDefaultClaimsLedgerClient();
    resetSyntheticClaimsDataset();
    resetClaimsListDelayForTests();
    clearSession();
  });

  it('Levels 0–6 regressions pass', () => {
    expect(runNegativeScopeScan().violations).toEqual([]);
    expect(runLevel1NegativeScopeScan().violations).toEqual([]);
    expect(runLevel2NegativeScopeScan().violations).toEqual([]);
    expect(runLevel3NegativeScopeScan().violations).toEqual([]);
    expect(runLevel4NegativeScopeScan().violations).toEqual([]);
    expect(runLevel5NegativeScopeScan().violations).toEqual([]);
    expect(runLevel6NegativeScopeScan().violations).toEqual([]);
    expect(runPrivacyScan().violations).toEqual([]);
    expect(runTokenAudit().violations).toEqual([]);
    expect(runFinancialScan().violations).toEqual([]);
  });

  it('Level 7 scope scan passes', () => {
    expect(runLevel7NegativeScopeScan().violations).toEqual([]);
  });

  it('Level 7 routes exist', () => {
    expect(assertLevel7RoutesExist()).toEqual({ ok: true, missing: [] });
  });

  it('source integrity probes pass on clean tree', () => {
    const results = runLevel7SourceIntegrityProbes();
    expect(results.every((r) => r.ok)).toBe(true);
  });
});

describe('Level 7 Harness — Five primary route shells', () => {
  beforeEach(() => {
    resetAuthStateForTests();
    resetGovernanceStateForTests();
    seedShellAuth('owner');
  });

  it.each([
    ['/app/claims', 'data-claims-ledger-page', 'Revenue Claims'],
    ['/app/trust', 'data-trust-index-page', /TrustEnvelopes/i],
    ['/app/channels', 'data-channels-page', /^Channels$/i],
    ['/app/exceptions', 'data-exceptions-page', /^Exceptions$/i],
    ['/app/budget', 'data-budget-page', /Budget Simulation Input/i],
  ] as const)('renders %s', async (path, selector, heading) => {
    renderShell(path);
    await waitFor(() => expect(document.querySelector(`[${selector}]`)).toBeInTheDocument());
    expect(screen.getAllByText(heading).length).toBeGreaterThan(0);
    expect(screen.queryByRole('heading', { name: /Command Center dashboard/i })).not.toBeInTheDocument();
  });

  it('redirects retired /app/benchmarks to channels overview', async () => {
    renderShell('/app/benchmarks');
    await waitFor(() => expect(document.querySelector('[data-channels-page]')).toBeInTheDocument());
    expect(screen.queryByRole('heading', { name: /Benchmark Intelligence/i })).not.toBeInTheDocument();
  });
});

describe('Level 7 Harness — Routes and guards', () => {
  beforeEach(() => {
    resetAuthStateForTests();
    resetGovernanceStateForTests();
    seedShellAuth('owner');
  });

  it('redirect guard allows Level 7 routes', () => {
    for (const route of LEVEL7_PERMITTED_ROUTES) {
      expect(resolveSafeRedirect(route, { hasSession: true, hasTenant: true }, '/app').ok).toBe(true);
    }
  });

  it('redirect guard permits billing route at Level 11', () => {
    expect(LEVEL8_PLUS_BLOCKED_ROUTES).not.toContain('/settings/billing');
    expect(resolveSafeRedirect('/settings/billing', { hasSession: true, hasTenant: true }, '/app')).toEqual({
      ok: true,
      path: '/app/settings/billing',
    });
  });

  it('Level 8 detail routes are not parent-ledger blocked shells', async () => {
    renderShell('/app/claims');
    await waitFor(() => expect(document.querySelector('[data-claims-ledger-page]')).toBeInTheDocument());
    expect(document.querySelector('[data-level8-blocked-route]')).not.toBeInTheDocument();
  });
});

describe('Level 7 Harness — Composite DTO and bounded network', () => {
  beforeEach(() => {
    resetLedgerRequestCounter();
    resetGovernanceStateForTests();
    setCurrentUserRole('owner');
    establishTenant(createMockSession(), createMockTenant());
  });

  it('25-row page uses bounded request count', async () => {
    const client = createClaimsLedgerClient();
    await client.listClaims('tenant_1', { pageSize: 25, offset: 0 });
    expect(getLedgerRequestCount()).toBeLessThanOrEqual(3);
  });

  it('default claims page returns at most 10 rows', async () => {
    setSyntheticClaimsDataset(244);
    const client = createClaimsLedgerClient();
    const outcome = await client.listClaims('tenant_1', { offset: 0 });
    expect(outcome.kind).toBe('loaded');
    if (outcome.kind === 'loaded') {
      expect(outcome.rows.length).toBeLessThanOrEqual(10);
      expect(outcome.pageSize).toBe(10);
    }
  });

  it('1k dataset does not increase request count', async () => {
    setSyntheticClaimsDataset(1000);
    const client = createClaimsLedgerClient();
    await client.listClaims('tenant_1', { pageSize: 25, offset: 0 });
    const count = getLedgerRequestCount();
    resetLedgerRequestCounter();
    await client.listClaims('tenant_1', { pageSize: 25, offset: 500 });
    expect(getLedgerRequestCount()).toBe(count);
  });

  it('10k claims dataset keeps request count bounded', async () => {
    setSyntheticClaimsDataset(10000);
    const client = createClaimsLedgerClient();
    await client.listClaims('tenant_1', { pageSize: 25, offset: 0 });
    expect(getLedgerRequestCount()).toBeLessThanOrEqual(3);
  });

  it('50k claims dataset keeps request count bounded', async () => {
    setSyntheticClaimsDataset(50000);
    const client = createClaimsLedgerClient();
    await client.listClaims('tenant_1', { pageSize: 25, offset: 0 });
    expect(getLedgerRequestCount()).toBeLessThanOrEqual(3);
  });

  it('10k trust index dataset keeps request count bounded', async () => {
    setSyntheticTrustIndexDataset(10000);
    const client = createTrustIndexClient();
    await client.listEnvelopes('tenant_1', { pageSize: 25, offset: 0 });
    expect(getLedgerRequestCount()).toBeLessThanOrEqual(3);
  });

  it('50k trust index dataset keeps request count bounded', async () => {
    setSyntheticTrustIndexDataset(50000);
    const client = createTrustIndexClient();
    await client.listEnvelopes('tenant_1', { pageSize: 25, offset: 0 });
    expect(getLedgerRequestCount()).toBeLessThanOrEqual(3);
  });

  it('rejects forbidden list envelope fields', () => {
    const bad = validateListDtoBoundary({ fullEnvelope: {} }, FORBIDDEN_LIST_ENVELOPE_FIELDS);
    expect(bad.ok).toBe(false);
  });
});

describe('Level 7 Harness — Query parser and URL persistence', () => {
  it('parses valid complex query', () => {
    const result = parseCanonicalClaimsQuery(
      '?claimSource=meta_ads&sort=discrepancy&sortDir=desc&offset=25&search=claim_01&sortDir=desc',
    );
    expect(result.filters.claimSource).toBe('meta_ads');
    expect(result.filters.sortKey).toBe('discrepancy');
    expect(result.filters.offset).toBe(25);
  });

  it('canonicalizes invalid sort key', () => {
    const result = parseCanonicalClaimsQuery('?sort=not_a_real_key');
    expect(result.isCanonical).toBe(false);
    expect(result.filters.sortKey).toBe('lastUpdated');
    expect(result.canonicalSearch).toContain('sort=lastUpdated');
  });

  it('rejects negative offset and caps huge page size', () => {
    const negative = parseCanonicalClaimsQuery('?offset=-5');
    expect(negative.isCanonical).toBe(false);
    expect(negative.filters.offset).toBeUndefined();

    const huge = parseCanonicalClaimsQuery('?pageSize=9999');
    expect(huge.isCanonical).toBe(false);
    expect(huge.filters.pageSize).toBeUndefined();

    const legacy = parseCanonicalClaimsQuery('?pageSize=25');
    expect(legacy.isCanonical).toBe(false);
    expect(legacy.filters.pageSize).toBeUndefined();
  });

  it('rejects malformed date range', () => {
    const bad = parseCanonicalClaimsQuery('?dateFrom=not-a-date');
    expect(bad.isCanonical).toBe(false);
  });

  it('loads filtered claims from URL in shell', async () => {
    seedShellAuth('owner');
    renderShell('/app/claims?claimSource=meta_ads&sort=discrepancy&sortDir=desc');
    await waitFor(() => expect(document.querySelector('[data-claims-ledger-page]')).toBeInTheDocument());
    expect(window.location.pathname).toBeDefined();
  });
});

describe('Level 7 Harness — Server-side query semantics', () => {
  it('global sort places high discrepancy on page 1', () => {
    const items = createSyntheticDataset((i) => ({ id: i, discrepancy: i }), 100);
    const result = executeServerQuery('claims', {
      items,
      params: { offset: 0, pageSize: 25, sortKey: 'discrepancy', sortDirection: 'desc' },
      defaultSortKey: 'discrepancy',
      getSortValue: (row) => row.discrepancy,
    });
    expect('error' in result).toBe(false);
    if (!('error' in result)) {
      expect(result.rows[0]?.discrepancy).toBe(99);
    }
  });

  it('filter is global not page-local', () => {
    const items = createSyntheticDataset((i) => ({ id: i, source: i % 2 === 0 ? 'meta_ads' : 'google_ads' }), 50);
    const result = executeServerQuery('claims', {
      items,
      params: { offset: 0, pageSize: 25, filters: { claimSource: 'meta_ads' } },
      defaultSortKey: 'id',
      filterFn: (row, f) => !f.claimSource || row.source === f.claimSource,
      getSortValue: (row) => row.id,
    });
    expect('error' in result).toBe(false);
    if (!('error' in result)) {
      expect(result.metadata.totalCount).toBe(25);
    }
  });
});

describe('Level 7 Harness — DOM cardinality', () => {
  it('caps DOM rows at MAX_DOM_TABLE_ROWS', () => {
    const rows = createSyntheticDataset((i) => ({ ...baseClaimRow(i), claimRef: `c_${i}` }), 100);
    const { container } = render(
      <ClaimsLedgerTable
        rows={rows.slice(0, MAX_DOM_TABLE_ROWS)}
        pagination={{ totalCount: 100, offset: 0, pageSize: 10, hasMore: true }}
      />,
    );
    expect(getTableDomRowCount(container)).toBeLessThanOrEqual(MAX_DOM_TABLE_ROWS);
  });
});

describe('Level 7 Harness — Financial truth', () => {
  it('claims table source uses operator labels and difference semantics', () => {
    const source = readFileSync(
      join(process.cwd(), 'src', 'components', 'claims', 'ClaimsLedgerTable', 'ClaimsLedgerTable.tsx'),
      'utf8',
    );
    const cells = readFileSync(
      join(process.cwd(), 'src', 'components', 'claims', 'ClaimsLedgerTable', 'ClaimsLedgerTableCells.tsx'),
      'utf8',
    );
    expect(source).toContain('CLAIMS_LEDGER_COLUMNS');
    expect(cells).toContain('DiscrepancyIndicator');
    expect(cells).toContain('data-claimed-revenue-minor');
    expect(cells).not.toContain('data-discrepancy-backend');
    expect(cells).not.toMatch(/parseFloat|\.toFixed/);
  });

  it('trust index table renders ten-column CRHAID forensic architecture', async () => {
    seedShellAuth('owner');
    renderShell('/app/trust');
    await waitFor(() =>
      expect(document.querySelectorAll('[data-trust-index-table] thead th')).toHaveLength(10),
    );
    expect(screen.getByRole('columnheader', { name: /Claim time/i })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /Claim source/i })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /Claimed revenue/i })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /Verified revenue/i })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /Difference/i })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /Match verdict/i })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /Attribution model/i })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /Confidence/i })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /Policy authority/i })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /^Audit$/i })).toBeInTheDocument();
    expect(screen.queryByRole('columnheader', { name: /Select/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('columnheader', { name: /Benchmark/i })).not.toBeInTheDocument();
    await waitFor(() =>
      expect(document.querySelectorAll('[data-discrepancy-indicator]').length).toBeGreaterThan(0),
    );
    expect(document.querySelector('[data-verified-revenue-minor]')).toBeTruthy();
    expect(document.querySelector('[data-claimed-revenue-minor]')).toBeTruthy();
    expect(document.querySelector('[data-trust-index-difference]')).toBeTruthy();
    expect(document.querySelector('[data-discrepancy-percent]')?.textContent).toMatch(/of claim/);
    expect(document.querySelector('[data-match-verdict]')).toBeTruthy();
    expect(document.querySelector('[data-trust-index-audit-open]')).toBeTruthy();
    const confidenceCells = document.querySelectorAll('[data-trust-index-confidence]');
    expect(confidenceCells.length).toBeGreaterThan(0);
    for (const cell of confidenceCells) {
      expect(cell.textContent).not.toMatch(/^\s*\d+%\s*$/);
    }
  });

  it('TrustEnvelope audit references resolve through the Tier B forensic record', async () => {
    const user = userEvent.setup();
    seedShellAuth('owner');
    renderShell('/app/trust');

    const links = await screen.findAllByRole('link', { name: /Open audit record/i });
    const href = links[0].getAttribute('href');
    expect(href).toMatch(/^\/app\/audit\?log=forensic&/);
    expect(href).toContain('eventId=evt_trust_envelope_');
    expect(href).toContain('envelopeId=env_');

    await user.click(links[0]);
    await waitFor(() =>
      expect(document.querySelector('[data-audit-forensic-detail-loaded]')).toBeInTheDocument(),
    );
    expect(document.querySelector('[data-audit-forensic-detail-missing]')).toBeNull();
  });

  it('keeps the ledger default in Tier A while envelope references explicitly select Tier B', () => {
    expect(buildAuditReferenceHref('aud_read_001')).toBe('/app/audit?log=access&eventId=aud_read_001');
    expect(buildTrustEnvelopeAuditReferenceHref('evt_env_001', 'env_0001')).toBe(
      '/app/audit?log=forensic&envelopeId=env_0001&eventId=evt_env_001',
    );
  });

  it('trust index header exposes target framing, freshness, policy notice, and actions', async () => {
    seedShellAuth('owner');
    renderShell('/app/trust');
    await waitFor(() => expect(document.querySelector('[data-trust-index-header]')).toBeInTheDocument());
    expect(screen.getByRole('heading', { name: /TrustEnvelopes/i })).toBeInTheDocument();
    expect(
      screen.getByText(
        /Canonical trust objects for verified revenue claims, attribution context, policy authority, audit artifacts, and signed JRF evidence/i,
      ),
    ).toBeInTheDocument();
    await waitFor(() => expect(document.querySelector('[data-trust-index-last-updated]')).toBeInTheDocument());
    expect(document.querySelector('[data-trust-index-last-updated]')?.textContent).toMatch(/^Updated /i);
    expect(document.querySelector('[data-trust-index-last-updated]')?.textContent).not.toMatch(/Source: Trust API/i);
    expect(document.querySelector('[data-trust-index-header-meta]')).toBeTruthy();
    expect(
      document.querySelector('[data-trust-index-header-actions]')?.compareDocumentPosition(
        document.querySelector('[data-trust-index-last-updated]')!,
      ) & Node.DOCUMENT_POSITION_PRECEDING,
    ).toBeTruthy();
    await waitFor(() => expect(document.querySelector('[data-trust-index-policy-notice]')).toBeInTheDocument());
    expect(document.querySelector('[data-trust-index-open-latest]')).toBeTruthy();
    const exportButton = screen.getByRole('button', { name: /Export selected artifacts/i });
    expect(exportButton).toBeDisabled();
    expect(screen.queryByText(/Bounded index rows only/i)).not.toBeInTheDocument();
  });

  it('trust index export remains disabled without row selection affordance', async () => {
    seedShellAuth('owner');
    renderShell('/app/trust');
    await waitFor(() => expect(document.querySelector('[data-trust-index-table]')).toBeInTheDocument());

    const exportButton = screen.getByRole('button', { name: /Export selected artifacts/i });
    expect(exportButton).toBeDisabled();
    expect(document.querySelector('[data-trust-index-row-checkbox]')).toBeNull();
    expect(document.querySelector('[data-trust-index-select-all]')).toBeNull();
  });

  it('trust index summary row exposes four aggregate metrics', async () => {
    seedShellAuth('owner');
    renderShell('/app/trust');
    await waitFor(() => expect(document.querySelector('[data-trust-index-summary-row]')).toBeInTheDocument());
    await waitFor(() => {
      const count = Number(
        document
          .querySelector('[data-unavailable-confidence-count]')
          ?.getAttribute('data-unavailable-confidence-count'),
      );
      expect(count).toBeGreaterThan(0);
    });
    expect(document.querySelector('[data-summary-metric="total_count"]')).toBeTruthy();
    expect(document.querySelector('[data-summary-metric="verified_revenue"]')).toBeTruthy();
    expect(document.querySelector('[data-summary-metric="audit_linked"]')).toBeTruthy();
    expect(document.querySelector('[data-summary-metric="unavailable_confidence"]')).toBeTruthy();
    expect(document.querySelector('[data-summary-metric-value="total_count"]')?.textContent).toMatch(/\d+/);
    expect(screen.getByText(/added in the last 24h/i)).toBeInTheDocument();
    expect(
      document.querySelector('[data-summary-metric="verified_revenue"]')?.textContent,
    ).toMatch(/Verified revenue/i);
    expect(screen.getByText(/Audit records linked/i)).toBeInTheDocument();
    expect(screen.getByText(/^Unavailable confidence$/i)).toBeInTheDocument();
    expect(document.querySelector('[data-unavailable-confidence-meta]')).toBeTruthy();
    expect(document.querySelector('[data-summary-drilldown="unavailable_confidence"]')).toBeTruthy();
    expect(
      document.querySelector('[data-summary-metric="total_count"] [data-trust-chip]'),
    ).toBeNull();
    expect(
      document.querySelector('[data-summary-metric="audit_linked"] [data-trust-chip]'),
    ).toBeNull();
  });

  it('trust index filters render four enum controls and mutate URL search', async () => {
    seedShellAuth('owner');
    const router = createClaimsShellRouter(['/app/trust']);
    const user = userEvent.setup();
    render(<RouterProvider router={router} />);
    await waitFor(() => expect(document.querySelector('[data-trust-index-filters]')).toBeInTheDocument());
    expect(screen.getByLabelText(/Verification status/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Discrepancy class/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Policy authority/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Confidence availability/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/Benchmark source/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Search by envelope ID/i)).not.toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText(/Policy authority/i), 'approval_required');
    await waitFor(() => expect(router.state.location.search).toContain('policyAuthority=approval_required'));

    await user.selectOptions(screen.getByLabelText(/Discrepancy class/i), 'material');
    await waitFor(() => expect(router.state.location.search).toContain('discrepancyClass=material'));
  });

  it('trust index sort toggle controls table ordering', async () => {
    seedShellAuth('owner');
    const router = createClaimsShellRouter(['/app/trust']);
    const user = userEvent.setup();
    render(<RouterProvider router={router} />);
    await waitFor(() => expect(document.querySelector('[data-trust-index-table-shell]')).toBeInTheDocument());

    expect(document.querySelector('[data-trust-index-sort]')).toBeInTheDocument();
    expect(document.querySelector('[data-trust-index-density]')).toBeFalsy();
    expect(document.querySelector('[data-trust-index-toolbar]')).toBeNull();

    await user.click(document.querySelector('[data-trust-index-sort-option="oldest_claim"]') as HTMLButtonElement);
    await waitFor(() => expect(router.state.location.search).toContain('sortDirection=asc'));
    expect(document.querySelector('[data-trust-index-table] [class*="tableWrapDense"]')).toBeTruthy();
  });
});

describe('Level 7 Harness — ConfidenceCell semantics', () => {
  it('renders shaped confidence interval', () => {
    render(
      <ConfidenceCell
        confidence={{
          status: 'available',
          intervalLower: 0.82,
          intervalUpper: 0.94,
          methodOrContext: 'Bayesian posterior',
        }}
      />,
    );
    expect(screen.getByText(/0\.82–0\.94/)).toBeInTheDocument();
    expect(screen.getByText(/Bayesian posterior/)).toBeInTheDocument();
    expect(document.querySelector('[data-confidence-cell="shaped"]')).toBeInTheDocument();
  });

  it('renders unavailable confidence reason', () => {
    render(
      <ConfidenceCell confidence={{ status: 'unavailable', reason: 'Cold start — insufficient data' }} />,
    );
    expect(screen.getByText(/Cold start — insufficient data/)).toBeInTheDocument();
    expect(document.querySelector('[data-confidence-cell="unavailable"]')).toBeInTheDocument();
  });

  it('rejects naked scalar confidence shape', () => {
    render(<ConfidenceCell confidence={{ status: 'available' }} />);
    expect(screen.getByRole('alert')).toHaveTextContent(/Invalid confidence shape/i);
    expect(document.querySelector('[data-confidence-cell="naked-scalar"]')).toBeInTheDocument();
  });
});

describe('Level 7 Harness — BenchmarkCell semantics', () => {
  it('renders available benchmark values without evidence-class badges', () => {
    render(
      <BenchmarkCell
        benchmark={{
          status: 'available',
          evidenceClass: 'live_empirical',
          coverageClass: 'exact',
          decisionSafeBenchmark: '12%',
          rawBenchmark: '14%',
        }}
      />,
    );
    expect(screen.queryByText('Live Skeldir Empirical')).not.toBeInTheDocument();
    expect(screen.queryByText('Exact')).not.toBeInTheDocument();
    expect(screen.getByText(/Raw: 14%/)).toBeInTheDocument();
    expect(screen.getByText(/Decision-safe: 12%/)).toBeInTheDocument();
    expect(document.querySelector('[data-benchmark-cell="available"]')).toBeInTheDocument();
  });

  it('renders unavailable benchmark reason', () => {
    render(
      <BenchmarkCell benchmark={{ status: 'unavailable', reason: 'No defensible benchmark exists yet.' }} />,
    );
    expect(screen.getByText(/No defensible benchmark exists yet/i)).toBeInTheDocument();
  });

  it('renders suppressed benchmark reason', () => {
    render(
      <BenchmarkCell
        benchmark={{ status: 'suppressed', suppressionReason: 'Dominance suppression — k-anonymity gate' }}
      />,
    );
    expect(screen.getByText(/Dominance suppression/i)).toBeInTheDocument();
    expect(document.querySelector('[data-benchmark-cell="suppressed"]')).toBeInTheDocument();
  });

  it('does not render blank or zero for unavailable benchmark', () => {
    const { container } = render(
      <BenchmarkCell benchmark={{ status: 'unavailable', reason: 'Coverage too sparse' }} />,
    );
    expect(container.textContent).not.toMatch(/^0$/);
    expect(container.textContent).not.toMatch(/^\s*$/);
  });
});

describe('Level 7 Harness — Interaction accessibility', () => {
  const sampleRows = createSyntheticDataset((i) => ({ ...baseClaimRow(i), claimRef: `c_${i}` }), 3);

  it('keeps table caption available to assistive tech without visible caption chrome', () => {
    render(
      <ClaimsLedgerTable
        rows={sampleRows}
        pagination={{ totalCount: 3, offset: 0, pageSize: 10, hasMore: false, onNext: vi.fn(), onPrevious: vi.fn() }}
      />,
    );
    expect(screen.getByRole('table', { name: /Forensic line-item ledger/i })).toBeInTheDocument();
    const caption = document.querySelector('[data-claims-ledger-table] caption');
    expect(caption).toBeTruthy();
    expect(caption?.className).toMatch(/srOnly/);
  });

  it('filter form has accessible label', () => {
    seedShellAuth('owner');
    renderShell('/app/claims');
    return waitFor(() => {
      expect(screen.getByLabelText(/Claims ledger filters/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Search by claim reference/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Date range/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Discrepancy class/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Policy authority/i)).toBeInTheDocument();
    });
  });

  it('pagination previous/next keyboard Enter and Space activation', async () => {
    const onNext = vi.fn();
    const onPrevious = vi.fn();
    render(
      <ClaimsLedgerTable
        rows={sampleRows}
        pagination={{
          totalCount: 100,
          offset: 25,
          pageSize: 10,
          hasMore: true,
          onNext,
          onPrevious,
        }}
      />,
    );
    const user = userEvent.setup();
    const next = screen.getByRole('button', { name: /Next page/i });
    const prev = screen.getByRole('button', { name: /Previous page/i });
    next.focus();
    await user.keyboard('{Enter}');
    expect(onNext).toHaveBeenCalled();
    prev.focus();
    await user.keyboard(' ');
    expect(onPrevious).toHaveBeenCalled();
  });

  it('detail affordance keyboard activation', async () => {
    const rows = createSyntheticDataset((i) => ({ ...baseClaimRow(i), claimRef: `c_${i}` }), 1);
    render(
      <MemoryRouter>
        <ClaimsLedgerTable
          rows={rows}
          pagination={{ totalCount: 1, offset: 0, pageSize: 10, hasMore: false }}
        />
      </MemoryRouter>,
    );
    const user = userEvent.setup();
    const link = screen.getByRole('link', { name: /Open claim record for c_0/i });
    link.focus();
    await user.keyboard('{Enter}');
    expect(link).toHaveAttribute('data-audit-open-affordance', 'navigate');
  });
});

describe('Level 7 Harness — Router URL state (behavioral)', () => {
  beforeEach(() => {
    resetAuthStateForTests();
    resetGovernanceStateForTests();
    resetClaimsListDelayForTests();
    resetSyntheticClaimsDataset();
    seedShellAuth('owner');
  });

  it('filter change mutates router search query', async () => {
    const router = createClaimsShellRouter(['/app/claims']);
    renderClaimsRouter(router);
    await waitForClaimsTableRows();
    const user = userEvent.setup();
    await user.selectOptions(claimsClaimSourceFilter(), 'meta_ads');
    await waitFor(() => expect(routerSearch(router)).toContain('claimSource=meta_ads'));
    expect(claimsClaimSourceFilter()).toHaveValue('meta_ads');
    await waitFor(() => expect(screen.getByRole('list', { name: /Active filters/i })).toBeInTheDocument());
    expect(within(screen.getByRole('list', { name: /Active filters/i })).getByText('Meta Ads')).toBeInTheDocument();
  });

  it('dimension filters combine with AND logic in URL and chips', async () => {
    const router = createClaimsShellRouter(['/app/claims']);
    renderClaimsRouter(router);
    await waitForClaimsTableRows();
    const user = userEvent.setup();
    await user.selectOptions(claimsClaimSourceFilter(), 'meta_ads');
    await user.selectOptions(claimsCampaignClassFilter(), 'paid_search');
    await waitFor(() => {
      const search = routerSearch(router);
      expect(search).toContain('claimSource=meta_ads');
      expect(search).toContain('campaignClass=paid_search');
    });
    const chips = within(screen.getByRole('list', { name: /Active filters/i }));
    expect(chips.getByText('Meta Ads')).toBeInTheDocument();
    expect(chips.getByText('Paid Search')).toBeInTheDocument();
  });

  it('sort change mutates router search query', async () => {
    const router = createClaimsShellRouter(['/app/claims']);
    renderClaimsRouter(router);
    await waitForClaimsTableRows();
    const user = userEvent.setup();
    await user.selectOptions(claimsSortFilter(), 'discrepancy');
    await waitFor(() => {
      expect(routerSearch(router)).toContain('sort=discrepancy');
      expect(routerSearch(router)).toContain('sortDir=desc');
    });
  });

  it('mounted claims table renders at most 10 supervisory rows', async () => {
    setSyntheticClaimsDataset(244);
    const router = createClaimsShellRouter(['/app/claims']);
    renderClaimsRouter(router);
    await waitForClaimsTableRows();
    const rowCount = document.querySelectorAll('[data-claims-ledger-table] tbody tr').length;
    expect(rowCount).toBeLessThanOrEqual(10);
    expect(rowCount).toBeGreaterThan(0);
  });

  it('pagination Enter mutates router search offset', async () => {
    const router = createClaimsShellRouter(['/app/claims']);
    renderClaimsRouter(router);
    await waitForClaimsTableRows();
    const user = userEvent.setup();
    const next = screen.getByRole('button', { name: /Next page/i });
    next.focus();
    await user.keyboard('{Enter}');
    await waitFor(() => expect(routerSearch(router)).toContain('offset=10'));
  });

  it('history back restores claims query state A after navigating to B', async () => {
    const router = createClaimsShellRouter(['/app/claims']);
    renderClaimsRouter(router);
    await waitForClaimsTableRows();
    const user = userEvent.setup();
    const claimSource = claimsClaimSourceFilter();
    await user.selectOptions(claimSource, 'meta_ads');
    await waitFor(() => expect(routerSearch(router)).toContain('claimSource=meta_ads'));
    await user.selectOptions(claimSource, 'google_ads');
    await waitFor(() => expect(routerSearch(router)).toContain('claimSource=google_ads'));
    await router.navigate(-1);
    await waitFor(() => {
      expect(routerSearch(router)).toContain('claimSource=meta_ads');
      expect(claimSource).toHaveValue('meta_ads');
    });
  });

  it('history forward restores claims query state B', async () => {
    const router = createClaimsShellRouter(['/app/claims']);
    renderClaimsRouter(router);
    await waitForClaimsTableRows();
    const user = userEvent.setup();
    const claimSource = claimsClaimSourceFilter();
    await user.selectOptions(claimSource, 'meta_ads');
    await waitFor(() => expect(routerSearch(router)).toContain('claimSource=meta_ads'));
    await user.selectOptions(claimSource, 'google_ads');
    await waitFor(() => expect(routerSearch(router)).toContain('claimSource=google_ads'));
    await router.navigate(-1);
    await waitFor(() => expect(claimSource).toHaveValue('meta_ads'));
    await router.navigate(1);
    await waitFor(() => {
      expect(routerSearch(router)).toContain('claimSource=google_ads');
      expect(claimSource).toHaveValue('google_ads');
    });
  });

  it('deep-link initialization hydrates controls rows and query metadata', async () => {
    const deepLink =
      '/app/claims?claimSource=meta_ads&verificationStatus=partial&sort=discrepancy&sortDir=desc&offset=25&pageSize=25';
    const router = createClaimsShellRouter([deepLink]);
    renderClaimsRouter(router);
    await waitForClaimsTableRows();
    expect(claimsClaimSourceFilter()).toHaveValue('meta_ads');
    expect(claimsVerificationStatusFilter()).toHaveValue('partial');
    expect(claimsSortFilter()).toHaveValue('discrepancy');
    expect(routerSearch(router)).toContain('offset=25');
    expect(document.querySelector('[data-query-id]')).toBeTruthy();
    expect(screen.queryByText(/^Query:/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/schema_invalid|query_invalid/i)).not.toBeInTheDocument();
  });

  it('return from claim detail preserves ledger query params', async () => {
    const ledgerUrl = '/app/claims?claimSource=meta_ads&sort=discrepancy&sortDir=desc';
    const router = createClaimsShellRouter([ledgerUrl, '/app/claims/claim_0001'], 1);
    renderClaimsRouter(router);
    await waitFor(() => expect(document.querySelector('[data-claim-detail-loaded]')).toBeTruthy());
    await router.navigate(-1);
    await waitFor(() => {
      expect(router.state.location.pathname).toBe('/app/claims');
      expect(routerSearch(router)).toContain('claimSource=meta_ads');
      expect(routerSearch(router)).toContain('sort=discrepancy');
    });
    await waitForClaimsTableRows();
    expect(claimsClaimSourceFilter()).toHaveValue('meta_ads');
  });

  it('filter keyboard operation updates URL and rows', async () => {
    const router = createClaimsShellRouter(['/app/claims']);
    renderClaimsRouter(router);
    await waitForClaimsTableRows();
    const user = userEvent.setup();
    const claimSource = claimsClaimSourceFilter();
    for (let i = 0; i < 40 && document.activeElement !== claimSource; i += 1) {
      await user.tab();
    }
    expect(document.activeElement).toBe(claimSource);
    await user.selectOptions(claimSource, 'meta_ads');
    await waitFor(() => expect(routerSearch(router)).toContain('claimSource=meta_ads'));
    await waitFor(() => {
      const cells = Array.from(document.querySelectorAll('[data-claims-ledger-table] tbody tr td'));
      expect(cells.some((c) => c.textContent?.includes('Meta Ads'))).toBe(true);
    });
  });

  it('pagination keyboard Space changes URL offset on mounted page', async () => {
    const router = createClaimsShellRouter(['/app/claims?offset=25']);
    renderClaimsRouter(router);
    await waitForClaimsTableRows();
    const user = userEvent.setup();
    const prev = screen.getByRole('button', { name: /Previous page/i });
    prev.focus();
    await user.keyboard(' ');
    await waitFor(() => expect(routerSearch(router)).not.toContain('offset=25'));
  });

  it('date range preset mutates canonical dateFrom and dateTo in URL', async () => {
    const router = createClaimsShellRouter(['/app/claims']);
    renderClaimsRouter(router);
    await waitForClaimsTableRows();
    const user = userEvent.setup();
    await user.selectOptions(screen.getByLabelText(/^Date range$/i), 'last_30_days');
    await waitFor(() => {
      expect(routerSearch(router)).toMatch(/dateFrom=\d{4}-\d{2}-\d{2}/);
      expect(routerSearch(router)).toMatch(/dateTo=\d{4}-\d{2}-\d{2}/);
    });
    expect(
      within(screen.getByRole('list', { name: /Active filters/i })).getByText('Last 30 days'),
    ).toBeInTheDocument();
  });

  it('clear filters resets URL and removes active chips', async () => {
    const router = createClaimsShellRouter(['/app/claims?claimSource=meta_ads&verificationStatus=partial']);
    renderClaimsRouter(router);
    await waitForClaimsTableRows();
    const user = userEvent.setup();
    expect(screen.getByRole('list', { name: /Active filters/i })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /^Clear filters$/i }));
    await waitFor(() => expect(routerSearch(router)).toBe(''));
    expect(screen.queryByRole('list', { name: /Active filters/i })).not.toBeInTheDocument();
  });

  it('chip dismiss removes one filter dimension from URL', async () => {
    const router = createClaimsShellRouter(['/app/claims?claimSource=meta_ads&verificationStatus=partial']);
    renderClaimsRouter(router);
    await waitForClaimsTableRows();
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /Remove Meta Ads filter/i }));
    await waitFor(() => {
      expect(routerSearch(router)).not.toContain('claimSource=meta_ads');
      expect(routerSearch(router)).toContain('verificationStatus=partial');
    });
  });
});

describe('Level 7 Harness — Mobile compact row (375px semantics)', () => {
  it('preserves row identity and label association', async () => {
    const row = baseClaimRow(0);
    render(
      <CompactLedgerRow
        rowKey={row.claimRef}
        identity={<strong>{row.claimRef}</strong>}
        primaryFields={[
          { key: 'verified', label: 'Verified revenue', value: '$100' },
          { key: 'claimed', label: 'Platform claim', value: '$100' },
        ]}
        secondaryFields={[{ key: 'audit', label: 'Audit', value: row.auditReference }]}
      />,
    );
    const article = screen.getByLabelText(`Ledger row ${row.claimRef}`);
    expect(within(article).getByText('Verified revenue')).toBeInTheDocument();
    expect(within(article).getByText('Platform claim')).toBeInTheDocument();
    expect(within(article).getByText(row.claimRef)).toBeInTheDocument();
  });

  it('disclosure toggles via keyboard', async () => {
    const row = baseClaimRow(1);
    render(
      <CompactLedgerRow
        rowKey={row.claimRef}
        identity={row.claimRef}
        primaryFields={[{ key: 'verified', label: 'Verified revenue', value: '$100' }]}
        secondaryFields={[{ key: 'policy', label: 'Policy', value: 'blocked' }]}
      />,
    );
    const user = userEvent.setup();
    const toggle = screen.getByRole('button', { name: /Show additional row fields/i });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    toggle.focus();
    await user.keyboard('{Enter}');
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByText('Policy')).toBeInTheDocument();
  });

  it('375px viewport activates mobile ledger path with keyboard disclosure', async () => {
    setMobileViewport375();
    seedShellAuth('owner');
    renderShell('/app/claims');
    expect(window.matchMedia('(max-width: 767px)').matches).toBe(true);
    await waitFor(() => expect(document.querySelector('[data-ledger-mobile]')).toBeInTheDocument());
    await waitFor(() => expect(document.querySelector('[data-compact-ledger-row]')).toBeTruthy());
    const user = userEvent.setup();
    const toggle = await screen.findAllByRole('button', { name: /Show additional row fields/i });
    toggle[0].focus();
    await user.keyboard('{Enter}');
    expect(toggle[0]).toHaveAttribute('aria-expanded', 'true');
    const detailBtn = screen.getAllByRole('link', { name: /Open claim record for claim_/i })[0];
    detailBtn.focus();
    await user.keyboard('{Enter}');
    await waitFor(() => expect(document.querySelector('[data-claim-detail-loaded]')).toBeTruthy());
    resetViewport();
  });
});

describe('Level 7 Harness — State matrix', () => {
  beforeEach(() => {
    resetAuthStateForTests();
    resetGovernanceStateForTests();
    resetSyntheticClaimsDataset();
    seedShellAuth('owner');
  });

  it('claims permission_denied for billing_only', async () => {
    seedShellAuth('billing_only');
    renderShell('/app/claims');
    await waitFor(() => expect(screen.getByText(/permission/i)).toBeInTheDocument());
  });

  it('trust index permission_denied for billing_only', async () => {
    seedShellAuth('billing_only');
    renderShell('/app/trust');
    await waitFor(() => expect(screen.getByText(/permission/i)).toBeInTheDocument());
  });

  it('channels permission_denied for billing_only', async () => {
    seedShellAuth('billing_only');
    renderShell('/app/channels');
    await waitFor(() => expect(screen.getByText(/permission/i)).toBeInTheDocument());
  });

  it('retired benchmarks route redirects to channels for billing_only', async () => {
    seedShellAuth('billing_only');
    renderShell('/app/benchmarks');
    await waitFor(() => expect(screen.getByText(/permission/i)).toBeInTheDocument());
  });

  it('exceptions permission_denied for billing_only', async () => {
    seedShellAuth('billing_only');
    renderShell('/app/exceptions');
    await waitFor(() => expect(screen.getByText(/permission/i)).toBeInTheDocument());
  });

  it('budget permission_denied for billing_only', async () => {
    seedShellAuth('billing_only');
    renderShell('/app/budget');
    await waitFor(() => expect(screen.getByText(/permission/i)).toBeInTheDocument());
  });

  it('exceptions exposes review affordance for Level 8 drawer', async () => {
    renderShell('/app/exceptions');
    await waitFor(() => expect(document.querySelector('[data-exceptions-page]')).toBeInTheDocument());
    await waitFor(() => expect(document.querySelector('[data-exceptions-results]')).toBeTruthy());
    expect(screen.getAllByRole('button', { name: /^Review /i }).length).toBeGreaterThan(0);
  });

  it('budget shows disabled Level 9 submit', async () => {
    renderShell('/app/budget');
    await waitFor(() => expect(document.querySelector('[data-budget-page]')).toBeInTheDocument());
    expect(screen.getByRole('button', { name: /Submit proposal \(Level 9\)/i })).toBeDisabled();
  });

  it('sidebar omits retired benchmarks navigation entry', async () => {
    renderShell('/app/channels');
    await waitFor(() => expect(document.querySelector('[data-channels-page]')).toBeInTheDocument());
    expect(screen.queryByRole('link', { name: /^Benchmarks$/i })).not.toBeInTheDocument();
  });
});

describe('Level 7 Harness — Query transition and stale response', () => {
  beforeEach(() => {
    resetAuthStateForTests();
    resetGovernanceStateForTests();
    resetClaimsListDelayForTests();
    resetSyntheticClaimsDataset();
    seedShellAuth('owner');
  });

  it('shows updating banner when table is in transition', () => {
    const rows = createSyntheticDataset((i) => ({ ...baseClaimRow(i), claimRef: `c_${i}` }), 2);
    render(
      <ClaimsLedgerTable
        rows={rows}
        updating
        pagination={{ totalCount: 100, offset: 0, pageSize: 10, hasMore: true, onNext: vi.fn(), onPrevious: vi.fn() }}
      />,
    );
    expect(document.querySelector('[data-ledger-updating]')).toBeTruthy();
    expect(document.querySelector('[data-query-updating="true"]')).toBeTruthy();
    expect(document.querySelector('[data-ledger-updating]')).toHaveAttribute('aria-live', 'polite');
    expect(screen.getAllByRole('button', { name: /Open claim record for/i })[0]).toBeDisabled();
    expect(screen.getByRole('button', { name: /Next page/i })).toBeDisabled();
  });

  it('mounted claims page ignores late stale response when filter changes quickly', async () => {
    setSyntheticClaimsDataset(50);
    setClaimsListDelayBySourceForTests({ meta_ads: 450 });
    const router = createClaimsShellRouter(['/app/claims']);
    renderClaimsRouter(router);
    await waitForClaimsTableRows();
    const user = userEvent.setup();
    const claimSource = claimsClaimSourceFilter();
    await user.selectOptions(claimSource, 'meta_ads');
    await user.selectOptions(claimSource, 'google_ads');
    await waitFor(() => expect(routerSearch(router)).toContain('claimSource=google_ads'));
    await waitFor(() => {
      const sourceCells = Array.from(document.querySelectorAll('[data-claims-ledger-table] tbody tr td'));
      expect(sourceCells.some((c) => c.textContent?.includes('Google Ads'))).toBe(true);
    });
    await new Promise((r) => setTimeout(r, 550));
    expect(routerSearch(router)).toContain('claimSource=google_ads');
    expect(routerSearch(router)).not.toMatch(/claimSource=meta_ads/);
    const sourceCells = Array.from(document.querySelectorAll('[data-claims-ledger-table] tbody tr td'));
    expect(sourceCells.every((c) => !c.textContent?.includes('Meta Ads'))).toBe(true);
    expect(screen.getAllByRole('link', { name: /Open claim record for/i })[0]).toBeInTheDocument();
  });

  it('query transition disables pagination and detail affordances while updating', async () => {
    setSyntheticClaimsDataset(50);
    setClaimsListDelayBySourceForTests({ meta_ads: 600 });
    const router = createClaimsShellRouter(['/app/claims']);
    renderClaimsRouter(router);
    await waitForClaimsTableRows();
    const user = userEvent.setup();
    const claimSource = claimsClaimSourceFilter();
    await user.selectOptions(claimSource, 'meta_ads');
    await waitFor(() => expect(document.querySelector('[data-ledger-updating]')).toBeTruthy());
    expect(screen.getByRole('button', { name: /Next page/i })).toBeDisabled();
    expect(screen.getAllByRole('button', { name: /Open claim record for/i })[0]).toBeDisabled();
    await waitFor(() => expect(document.querySelector('[data-ledger-updating]')).toBeFalsy(), { timeout: 3000 });
  });
});

describe('Level 7 Harness — Detail navigation UX', () => {
  beforeEach(() => {
    seedShellAuth('owner');
  });

  it('detail affordance navigates to claim detail', async () => {
    renderShell('/app/claims');
    await waitFor(() => expect(document.querySelector('[data-claims-ledger-table] tbody tr, [data-compact-ledger-row]')).toBeTruthy());
    const user = userEvent.setup();
    const btn = await screen.findAllByRole('link', { name: /Open claim record for claim_/i });
    await user.click(btn[0]);
    await waitFor(() => expect(document.querySelector('[data-claim-detail-loaded]')).toBeTruthy());
  });
});

describe('Level 7 Harness — Channels overview remediation', () => {
  beforeEach(() => {
    resetAuthStateForTests();
    resetGovernanceStateForTests();
    seedShellAuth('owner');
  });

  it('renders page header, metric basis control, summary row, filters, and channel trust table', async () => {
    renderShell('/app/channels');
    await waitFor(() => expect(document.querySelector('[data-channels-page]')).toBeInTheDocument());
    expect(screen.getByRole('heading', { name: /^Channels$/i })).toBeInTheDocument();
    expect(
      screen.getByText(/Verified channel performance from TrustEnvelope-backed claims/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Revenue shown here is verified commerce evidence unless explicitly marked/i),
    ).toBeInTheDocument();
    expect(document.querySelector('[data-channels-metric-basis]')).toBeTruthy();
    expect(screen.getByRole('radio', { name: /Verified revenue/i })).toHaveAttribute('aria-checked', 'true');
    await waitFor(() => expect(document.querySelector('[data-channels-summary-row]')).toBeInTheDocument());
    expect(document.querySelector('[data-summary-metric="highest_verified_revenue"]')).toBeTruthy();
    expect(document.querySelector('[data-summary-metric="largest_discrepancy"]')).toBeTruthy();
    expect(document.querySelector('[data-summary-metric="lowest_confidence"]')).toBeTruthy();
    expect(document.querySelector('[data-summary-metric="best_action_ready"]')).toBeTruthy();
    expect(document.querySelector('[data-channels-filters]')).toBeTruthy();
    await waitFor(() => expect(document.querySelector('[data-channels-trust-table]')).toBeInTheDocument());
    expect(screen.getByRole('heading', { name: /Channel trust/i })).toBeInTheDocument();
  });

  it('table renders six distinct channel intersections with separate attribution and claim-source columns', async () => {
    renderShell('/app/channels');
    await waitFor(() => expect(document.querySelector('[data-channel-link]')).toBeTruthy());
    const links = document.querySelectorAll('[data-channel-link]');
    expect(links.length).toBe(6);
    const attributionNames = Array.from(links).map((node) => node.textContent);
    expect(new Set(attributionNames).size).toBe(6);
    const table = document.querySelector('[data-channels-trust-table]');
    expect(table).toBeTruthy();
    expect(table?.textContent).toMatch(/Paid Search/);
    expect(table?.textContent).toMatch(/Paid Social/);
    expect(table?.textContent).toMatch(/Meta Ads/);
    expect(table?.textContent).toMatch(/Google Ads/);
    expect(table?.querySelectorAll('[data-attribution-channel]').length).toBe(6);
    expect(table?.querySelectorAll('[data-claim-source-cell]').length).toBe(6);
    expect(screen.getAllByRole('link', { name: /Open .+ channel detail/i }).length).toBeGreaterThan(0);
    expect(document.querySelector('[data-channels-pagination]')).toBeTruthy();
    expect(screen.getByText(/1–6 of 6/)).toBeInTheDocument();
  });

  it('platform-reported metric basis shows warning banner', async () => {
    const user = userEvent.setup();
    renderShell('/app/channels');
    await waitFor(() => expect(document.querySelector('[data-channels-metric-basis]')).toBeTruthy());
    await user.click(screen.getByRole('radio', { name: /Platform-reported revenue/i }));
    await waitFor(() => expect(document.querySelector('[data-channels-platform-warning]')).toBeTruthy());
    expect(
      screen.getByText(/Platform-reported revenue is a claim source, not verified truth/i),
    ).toBeInTheDocument();
  });

  it('table exposes text-only policy authority labels and sortable headers', async () => {
    renderShell('/app/channels');
    await waitFor(() => expect(document.querySelector('[data-channels-trust-table]')).toBeInTheDocument());
    const table = document.querySelector('[data-channels-trust-table]');
    const labels = table?.querySelectorAll('[data-status-text]');
    expect(labels?.length).toBeGreaterThanOrEqual(6);
    expect(table?.querySelector('[data-verified-revenue-minor] [data-status-text]')).toBeNull();
    expect(table?.querySelector('[data-claimed-revenue-minor] [data-status-text]')).toBeNull();
    expect(table?.textContent).not.toMatch(/deterministic.*deterministic/i);
    const discrepancyBadge = table?.querySelector('[data-discrepancy-badge][data-status-text]');
    expect(discrepancyBadge?.textContent?.trim()).toMatch(/^(Rejected|Flagged|Within tolerance|Unavailable)$/);
    const bayesianBadge = table?.querySelector('[data-bayesian-status][data-status-text]');
    expect(bayesianBadge?.textContent?.trim()).toMatch(/^(Healthy|Low confidence|Unavailable|Delayed)$/);
    expect(document.querySelector('[data-channels-sort="verifiedRevenue"]')).toBeTruthy();
    expect(document.querySelector('[data-channels-sort="attributionChannel"]')).toBeTruthy();
    expect(document.querySelector('[data-channels-sort="claimSource"]')).toBeTruthy();
    expect(document.querySelector('[data-channels-sort="policyAuthority"]')).toBeTruthy();
  });

  it('attribution channel and claim source sort clicks update canonical URL without sort_invalid', async () => {
    const router = createClaimsShellRouter(['/app/channels']);
    renderClaimsRouter(router);
    const user = userEvent.setup();
    await waitFor(() => expect(document.querySelector('[data-channels-sort="attributionChannel"]')).toBeTruthy());
    await user.click(document.querySelector('[data-channels-sort="attributionChannel"]') as HTMLElement);
    await waitFor(() => expect(routerSearch(router)).toContain('sortKey=attributionChannel'));
    expect(routerSearch(router)).toContain('sortDirection=desc');
    expect(screen.queryByText(/Invalid sort key/i)).not.toBeInTheDocument();

    await user.click(document.querySelector('[data-channels-sort="claimSource"]') as HTMLElement);
    await waitFor(() => expect(routerSearch(router)).toContain('sortKey=claimSource'));
    expect(screen.queryByText(/Invalid sort key/i)).not.toBeInTheDocument();
  });

  it('sort header click updates canonical URL search params', async () => {
    const router = createClaimsShellRouter(['/app/channels']);
    renderClaimsRouter(router);
    const user = userEvent.setup();
    await waitFor(() => expect(document.querySelector('[data-channels-sort="verifiedRevenue"]')).toBeTruthy());
    await user.click(document.querySelector('[data-channels-sort="verifiedRevenue"]') as HTMLElement);
    await waitFor(() => expect(routerSearch(router)).toContain('sortKey=verifiedRevenue'));
    expect(routerSearch(router)).toContain('sortDirection=desc');
  });
});

describe('Level 7 Harness — Claims ledger dimensional remediation', () => {
  beforeEach(() => {
    resetAuthStateForTests();
    resetGovernanceStateForTests();
    resetSyntheticClaimsDataset();
    seedShellAuth('owner');
  });

  it('renders three orthogonal dimension columns and forbids a Channel header', async () => {
    renderShell('/app/claims');
    await waitForClaimsTableRows();
    const table = document.querySelector('[data-claims-ledger-table]');
    expect(table).toBeTruthy();
    expect(screen.getByRole('columnheader', { name: /Claim source \(platform\)/i })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /^Campaign class$/i })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /^Commerce rail$/i })).toBeInTheDocument();
    expect(screen.queryByRole('columnheader', { name: /^Channel$/i })).not.toBeInTheDocument();
    expect(table?.querySelectorAll('[data-campaign-class]').length).toBeGreaterThan(0);
    expect(table?.querySelectorAll('[data-commerce-rail]').length).toBeGreaterThan(0);
  });

  it('exposes three independent dimension filters', async () => {
    renderShell('/app/claims');
    await waitForClaimsTableRows();
    expect(document.querySelector('[data-claims-dimension-filters]')).toBeTruthy();
    expect(claimsClaimSourceFilter()).toBeInTheDocument();
    expect(claimsCampaignClassFilter()).toBeInTheDocument();
    expect(claimsCommerceRailFilter()).toBeInTheDocument();
    expect(screen.getByLabelText(/^Commerce truth$/i)).toBeInTheDocument();
  });

  it('shows one forensic line item per claim without grouping rows', async () => {
    setSyntheticClaimsDataset(50);
    renderShell('/app/claims');
    await waitForClaimsTableRows();
    const rows = document.querySelectorAll('[data-claims-ledger-table] tbody tr');
    expect(rows.length).toBeGreaterThan(1);
    const claimRefs = new Set(
      Array.from(rows)
        .map((row) => row.querySelector('[data-audit-open-affordance]')?.getAttribute('href'))
        .filter(Boolean),
    );
    expect(claimRefs.size).toBe(rows.length);
  });
});

describe('Level 7 Harness — Permissions', () => {
  it('billing_only cannot view claims', () => {
    expect(canViewClaims('billing_only')).toBe(false);
  });
});

describe('Level 7 Harness — Sabotage', () => {
  it('clean tree passes integrity probes', () => {
    const results = runLevel7IntegrityProbes();
    expect(results.every((r) => r.ok)).toBe(true);
  });

  it('sabotage samples trigger detectors', () => {
    const clean = readFileSync(join(process.cwd(), 'src', 'claims', 'claimsClient.ts'), 'utf8');
    const sabotage = `${clean}\nuseEffect(() => fetch(\nrows.sort(\nfullEnvelope:\nparseFloat\nConfidence: 94%\nexportVerifiedReport(`;
    const probes = runLevel7SabotageProbes(sabotage);
    expect(probes.filter((p) => p.triggered).length).toBeGreaterThanOrEqual(5);
    const cleanProbes = runLevel7SabotageProbes(clean);
    expect(cleanProbes.filter((p) => p.triggered).length).toBe(0);
  });

  it('trust index omission sabotage triggers', () => {
    const bad = 'export function TrustEnvelopeIndexPage() { return <div>TrustEnvelopeIndex</div>; }';
    const probes = runLevel7SabotageProbes(bad);
    expect(probes.find((p) => p.name === 'trust-index-missing-financial-value')?.triggered).toBe(true);
    expect(probes.find((p) => p.name === 'trust-index-missing-confidence-cell')?.triggered).toBe(true);
  });
});
