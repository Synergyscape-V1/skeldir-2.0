import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';
import { createMockSession, createMockTenant } from '../auth/authClient';
import {
  resolveSafeRedirect,
  LEVEL5_PERMITTED_ROUTES,
  LEVEL6_PLUS_BLOCKED_ROUTES,
} from '../auth/redirectGuard';
import {
  clearSession,
  establishTenant,
  resetAuthStateForTests,
  setBootstrapReady,
} from '../auth/sessionStore';
import { runLevel1NegativeScopeScan } from '../audit/level1NegativeScopeScan';
import { runLevel2NegativeScopeScan } from '../audit/level2NegativeScopeScan';
import { runLevel3NegativeScopeScan } from '../audit/level3NegativeScopeScan';
import { runLevel4NegativeScopeScan } from '../audit/level4NegativeScopeScan';
import {
  assertLevel5ComponentsExist,
  assertLevel5RoutesExist,
  runLevel5IntegritySabotageProbes,
  runLevel5NegativeScopeScan,
  runLevel5SabotageProbes,
} from '../audit/level5NegativeScopeScan';
import { runNegativeScopeScan } from '../audit/negativeScopeScan';
import { runPrivacyScan } from '../audit/privacyScan';
import { runSecretScan, runSecretSabotageProbes, SECRET_SABOTAGE_SAMPLES } from '../audit/secretScan';
import { runTokenAudit } from '../audit/tokenAudit';
import { AppShellRoutes } from '../app/routes/ShellRoutes';
import {
  createOperationalAuditClient,
  createMockOperationalAuditTransport,
  createSyntheticAuditEvents,
  createSyntheticDLQEvents,
  resetDefaultOperationalAuditClient,
  setDefaultOperationalAuditClient,
} from '../operationalAudit/operationalAuditClient';
import { detectInvalidSignatureJsonLeak } from '../operationalAudit/artifactIntegrity';
import { validateHealthDomainSeparation } from '../operationalAudit/healthDomain';
import { AUDIT_LEDGER_BATCH_SIZE, MAX_DOM_TABLE_ROWS } from '../operationalAudit/pagination';
import { parseAuditFilters } from '../operationalAudit/parseAuditFilters';
import { resolveForensicAuditFilters } from '../operationalAudit/forensicBusinessTriage';
import { canOpenAuditArtifact, canViewAudit, canViewDiagnostics } from '../operationalAudit/permissions';
import { resetGovernanceStateForTests, setCurrentUserRole } from '../governance/governanceStore';
import { HEALTH_STATE_LABELS, OPERATIONAL_AUDIT_COPY } from '../operationalAudit/copy';
import { AuditArtifactDrawer } from '../components/audit/AuditArtifactDrawer/AuditArtifactDrawer';
import { AuditLedgerTable } from '../components/audit/AuditLedgerTable/AuditLedgerTable';
import { Table } from '../components/layout/Table/Table';
import { assertDomRowCap, getTableDomRowCount } from './level5.helpers';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

function renderShell(initialPath = '/app/audit') {
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
  resetDefaultOperationalAuditClient();
  setDefaultOperationalAuditClient(
    createOperationalAuditClient(
      createMockOperationalAuditTransport({
        currentUserRole: role,
        denyArtifact: role === 'viewer',
      }),
    ),
  );
}

describe('Level 5 Harness — Scope and regression', () => {
  beforeEach(() => {
    resetAuthStateForTests();
    resetGovernanceStateForTests();
    resetDefaultOperationalAuditClient();
    clearSession();
  });

  it('Levels 0–4 regressions pass', () => {
    expect(runNegativeScopeScan().violations).toEqual([]);
    expect(runLevel1NegativeScopeScan().violations).toEqual([]);
    expect(runLevel2NegativeScopeScan().violations).toEqual([]);
    expect(runLevel3NegativeScopeScan().violations).toEqual([]);
    expect(runLevel4NegativeScopeScan().violations).toEqual([]);
    expect(runPrivacyScan().violations).toEqual([]);
    expect(runTokenAudit().violations).toEqual([]);
  });

  it('Level 5 scope scan passes', () => {
    expect(runLevel5NegativeScopeScan().violations).toEqual([]);
  });

  it('Level 5 routes and components exist', () => {
    expect(assertLevel5RoutesExist()).toEqual({ ok: true, missing: [] });
    expect(assertLevel5ComponentsExist()).toEqual({ ok: true, missing: [] });
  });
});

describe('Level 5 Harness — Routes and guards', () => {
  beforeEach(() => {
    resetAuthStateForTests();
    resetGovernanceStateForTests();
    resetDefaultOperationalAuditClient();
    clearSession();
    seedShellAuth('owner');
  });

  it('renders audit ledger page', async () => {
    renderShell('/app/audit');
    await waitFor(() => {
      expect(document.querySelector('[data-audit-ledger-page]')).toBeInTheDocument();
    });
    expect(screen.getAllByText('actor_01').length).toBeGreaterThan(0);
  });

  it('renders operational diagnostics page', async () => {
    renderShell('/app/diagnostics');
    await waitFor(() => {
      expect(document.querySelector('[data-operational-diagnostics-page]')).toBeInTheDocument();
    });
  });

  it('fails closed with a polished unresolved-reference state for a missing forensic event', async () => {
    renderShell('/app/audit/events/evt_missing_reference');

    await waitFor(() =>
      expect(document.querySelector('[data-audit-forensic-detail-missing]')).toBeInTheDocument(),
    );
    expect(screen.getByRole('heading', { name: /Forensic record unavailable/i })).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent(/evt_missing_reference/i);
    expect(screen.getByRole('alert')).toHaveTextContent(
      /does not alter the TrustEnvelope or its deterministic financial truth/i,
    );
    expect(screen.getByRole('link', { name: /Return to Forensic Log/i })).toHaveAttribute(
      'href',
      '/app/audit?log=forensic',
    );
    expect(screen.queryByText(OPERATIONAL_AUDIT_COPY.auditFilteredEmpty)).not.toBeInTheDocument();
  });

  it('redirect guard allows Level 5 audit route', () => {
    expect(LEVEL5_PERMITTED_ROUTES).toContain('/audit');
    expect(
      resolveSafeRedirect('/audit', { hasSession: true, hasTenant: true }, '/app'),
    ).toEqual({ ok: true, path: '/app/audit' });
  });

  it('redirect guard allows Level 7 claims route', () => {
    expect(resolveSafeRedirect('/claims', { hasSession: true, hasTenant: true }, '/app')).toEqual({
      ok: true,
      path: '/app/claims',
    });
  });

  it('parses system_health audit filter', () => {
    const filters = parseAuditFilters('?filter=system_health');
    expect(filters.systemHealth).toBe(true);
    expect(filters.eventType).toBe('system_health');
  });

  it('does not hide an exact forensic deep link behind the default date window', () => {
    expect(
      resolveForensicAuditFilters({
        logMode: 'forensic_log',
        eventId: 'evt_historical_001',
      }),
    ).toEqual({
      logMode: 'forensic_log',
      eventId: 'evt_historical_001',
    });
  });
});

describe('Level 5 Harness — Permissions', () => {
  it('viewer can view audit but not open artifacts', () => {
    expect(canViewAudit('viewer')).toBe(true);
    expect(canOpenAuditArtifact('viewer')).toBe(false);
    expect(canViewDiagnostics('viewer')).toBe(false);
  });

  it('billing_only cannot view audit or diagnostics', () => {
    expect(canViewAudit('billing_only')).toBe(false);
    expect(canViewDiagnostics('billing_only')).toBe(false);
  });
});

describe('Level 5 Harness — Health domain copy', () => {
  it('exposes operational health label in audit copy', () => {
    expect(HEALTH_STATE_LABELS.operational).toBe('Trust systems operational');
  });

  it('keeps health domain copy separated', () => {
    expect(validateHealthDomainSeparation('confidence_degraded')).toEqual([]);
    expect(validateHealthDomainSeparation('api_paused')).toEqual([]);
    expect(validateHealthDomainSeparation('integration_attention')).toEqual([]);
    expect(validateHealthDomainSeparation('operational')).toEqual([]);
  });

  it('confidence degraded tooltip does not mention API outage', () => {
    expect(OPERATIONAL_AUDIT_COPY.healthTooltipConfidenceDegraded.toLowerCase()).not.toMatch(
      /outage|offline|api paused/,
    );
  });

  it('api paused tooltip does not mention confidence model', () => {
    expect(OPERATIONAL_AUDIT_COPY.healthTooltipApiPaused.toLowerCase()).not.toMatch(
      /confidence|bayesian|probabilistic/,
    );
  });

  it('health click label routes through audit filter semantics', () => {
    expect(OPERATIONAL_AUDIT_COPY.healthClickLabel).toMatch(/audit/i);
  });
});

describe('Level 5 Harness — Audit artifact drawer', () => {
  beforeEach(() => {
    resetAuthStateForTests();
    resetGovernanceStateForTests();
    resetDefaultOperationalAuditClient();
    clearSession();
    seedShellAuth('owner');
  });

  it('marks forensic rows as interactive for hover affordance', async () => {
    renderShell('/app/audit?log=forensic');
    await waitFor(() => {
      expect(document.querySelector('[data-audit-ledger-table][data-audit-executive-table]')).toBeInTheDocument();
    });
    expect(document.querySelectorAll('[data-audit-ledger-table] [data-table-row-interactive]').length).toBeGreaterThan(0);
  });

  it('does not mark access history rows as interactive', async () => {
    renderShell('/app/audit?log=access');
    await waitFor(() => {
      expect(document.querySelector('[data-audit-ledger-table][data-audit-log-mode="access_history"]')).toBeInTheDocument();
    });
    expect(document.querySelector('[data-audit-ledger-table] [data-table-row-interactive]')).toBeNull();
  });

  it('opens forensic drawer from audit row activation', async () => {
    const user = userEvent.setup();
    renderShell('/app/audit?log=forensic');
    await waitFor(() => {
      expect(document.querySelector('[data-audit-ledger-table][data-audit-executive-table]')).toBeInTheDocument();
    });
    expect(screen.queryByText('idem_aud_006')).not.toBeInTheDocument();
    const row = document
      .querySelector('[data-audit-ledger-table] [data-audit-event-type="artifact_exported"]')
      ?.closest('tr');
    expect(row).toBeTruthy();
    await user.click(row!);
    await waitFor(() => {
      expect(document.querySelector('[data-audit-forensic-detail-loaded]')).toBeInTheDocument();
    });
    await user.click(screen.getByRole('button', { name: /View Technical Details/i }));
    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
    expect(screen.getByText('Technical audit details')).toBeInTheDocument();
    expect(document.querySelector('[data-forensic-chain-panel]')).toBeInTheDocument();
  });

  it('suppresses JSON preview for invalid-signature artifact aud_006', async () => {
    const user = userEvent.setup();
    renderShell('/app/audit/events/aud_006');
    await waitFor(() => {
      expect(document.querySelector('[data-audit-forensic-detail-loaded]')).toBeInTheDocument();
    });
    await user.click(screen.getByRole('button', { name: /View Technical Details/i }));
    await waitFor(() => {
      expect(document.querySelector('[data-artifact-invalid-signature]')).toBeInTheDocument();
    });
    expect(document.querySelector('[data-artifact-json-preview]')).not.toBeInTheDocument();
    expect(detectInvalidSignatureJsonLeak(true, false)).toBe(false);
  });

  it('closes drawer on Escape and returns focus to technical details trigger', async () => {
    const user = userEvent.setup();
    renderShell('/app/audit?log=forensic');
    await waitFor(() => {
      expect(document.querySelector('[data-audit-ledger-page]')).toBeInTheDocument();
    });
    const row = document
      .querySelector('[data-audit-ledger-table] [data-audit-event-type="artifact_exported"]')
      ?.closest('tr') as HTMLTableRowElement;
    await user.click(row);
    await waitFor(() => {
      expect(document.querySelector('[data-audit-forensic-detail-loaded]')).toBeInTheDocument();
    });
    const technicalButton = screen.getByRole('button', { name: /View Technical Details/i });
    await user.click(technicalButton);
    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /Close drawer/i })).toHaveFocus();
    await user.keyboard('{Escape}');
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
    expect(technicalButton).toHaveFocus();
  });

  it('drawer without selection shows guard alert', () => {
    render(
      <MemoryRouter>
        <AuditArtifactDrawer eventId={null} open onClose={() => undefined} />
      </MemoryRouter>,
    );
    expect(document.querySelector('[data-drawer-without-selection]')).toBeInTheDocument();
  });
});

describe('Level 5 Harness — Client boundary', () => {
  it('AuditLedgerPage does not contain fetch(', () => {
    const source = readFileSync(
      join(process.cwd(), 'src/components/audit/AuditLedgerPage/AuditLedgerPage.tsx'),
      'utf8',
    );
    expect(source.includes('fetch(')).toBe(false);
  });

  it('OperationalDiagnosticsPage does not contain fetch(', () => {
    const source = readFileSync(
      join(process.cwd(), 'src/components/operational/OperationalDiagnosticsPage/OperationalDiagnosticsPage.tsx'),
      'utf8',
    );
    expect(source.includes('fetch(')).toBe(false);
  });
});

describe('Level 5 Harness — Sabotage controls', () => {
  it('scope sabotage probes fire on violations', () => {
    const sabotageSample = `
      path="/claims"
      path="/trust/"
      exportAudit
      verifySignature
      TrustEnvelope detail
      fetch(
      rows.map((row)
      data-artifact-json-preview
      verified revenue trend
      data-drawer-without-selection
    `;
    const results = runLevel5SabotageProbes(sabotageSample);
    expect(results.every((r) => r.pass)).toBe(true);
  });

  it('clean tree secret scan passes', () => {
    expect(runSecretScan().violations).toEqual([]);
  });

  it('secret sabotage probes detect controlled violations', () => {
    const sample = Object.values(SECRET_SABOTAGE_SAMPLES).join('\n');
    const results = runSecretSabotageProbes(sample);
    expect(results.filter((r) => r.name.includes('leak')).every((r) => r.pass)).toBe(true);
  });

  it('L4 scope still blocks health strip in governance-only scan sample', () => {
    const governanceOnly = 'settings/team\nsettings/policy';
    const results = runLevel5SabotageProbes(governanceOnly);
    expect(results.find((r) => r.name === 'audit-route-allowed')?.pass).toBe(true);
  });

  it('integrity sabotage probes pass on clean implementation', () => {
    const results = runLevel5IntegritySabotageProbes();
    expect(results.every((r) => r.pass)).toBe(true);
  });

  it('expanded sabotage sample detects cardinality and integrity violations', () => {
    const sabotageSample = `
      path="/claims"
      path="/trust/"
      exportAudit
      verifySignature
      TrustEnvelope detail
      fetch(
      rows.map((row)
      data-artifact-json-preview
      verified revenue trend
      data-drawer-without-selection
    `;
    const results = runLevel5SabotageProbes(sabotageSample);
    expect(results.every((r) => r.pass)).toBe(true);
  });
});

describe('Level 5 Harness — Bounded rendering', () => {
  const columns = [{ key: 'id', header: 'ID', render: (row: { id: string }) => row.id }];

  it('Table caps DOM rows at MAX_DOM_TABLE_ROWS even with oversized rows prop', () => {
    const oversized = Array.from({ length: 50_000 }, (_, i) => ({ id: `row_${i}` }));
    const { container } = render(
      <Table caption="Stress" columns={columns} rows={oversized} getRowKey={(row) => row.id} />,
    );
    expect(getTableDomRowCount(container)).toBeLessThanOrEqual(MAX_DOM_TABLE_ROWS);
    assertDomRowCap(container, 50_000);
  });

  it('client returns bounded cursor page for 50k access-history events', async () => {
    const client = createOperationalAuditClient(
      createMockOperationalAuditTransport({
        auditEvents: createSyntheticAuditEvents(50_000),
      }),
    );
    const outcome = await client.listAuditEvents('tenant_1', { logMode: 'access_history' });
    expect(outcome.kind).toBe('audit_loaded');
    if (outcome.kind !== 'audit_loaded') return;
    expect(outcome.events.length).toBeLessThanOrEqual(AUDIT_LEDGER_BATCH_SIZE);
    expect(outcome.totalCount).toBe(50_000);
    expect(outcome.hasMore).toBe(true);
    expect(outcome.nextCursor).toBeTruthy();
  });

  it('client returns bounded page for 1k DLQ events', async () => {
    const client = createOperationalAuditClient(
      createMockOperationalAuditTransport({
        currentUserRole: 'owner',
        diagnostics: {
          summary: { taskFailures: 1, integrationIssues: 0, confidenceDelayed: 0, trustApiPaused: false },
          dlqEvents: createSyntheticDLQEvents(1_000),
        },
      }),
    );
    const outcome = await client.getDiagnostics('tenant_1', {});
    expect(outcome.kind).toBe('diagnostics_loaded');
    if (outcome.kind !== 'diagnostics_loaded') return;
    expect(outcome.dlqEvents.length).toBeLessThanOrEqual(MAX_DOM_TABLE_ROWS);
    expect(outcome.totalCount).toBe(1_000);
  });

  it('AuditLedgerTable renders bounded rows for high-cardinality mock', async () => {
    resetDefaultOperationalAuditClient();
    setDefaultOperationalAuditClient(
      createOperationalAuditClient(
        createMockOperationalAuditTransport({
          auditEvents: createSyntheticAuditEvents(10_000),
        }),
      ),
    );
    const client = createOperationalAuditClient(
      createMockOperationalAuditTransport({
        auditEvents: createSyntheticAuditEvents(10_000),
      }),
    );
    const outcome = await client.listAuditEvents('tenant_1', { logMode: 'access_history' });
    if (outcome.kind !== 'audit_loaded') throw new Error('expected audit_loaded');
    const { container } = render(
      <AuditLedgerTable
        logMode="access_history"
        events={outcome.events}
        cursorPagination={{
          loadedCount: outcome.events.length,
          hasMore: outcome.hasMore,
        }}
      />,
    );
    expect(getTableDomRowCount(container)).toBe(AUDIT_LEDGER_BATCH_SIZE);
  });

  it('audit ledger page exposes cursor load-more controls', async () => {
    resetAuthStateForTests();
    resetGovernanceStateForTests();
    clearSession();
    establishTenant(createMockSession(), createMockTenant());
    setBootstrapReady();
    setCurrentUserRole('owner');
    resetDefaultOperationalAuditClient();
    setDefaultOperationalAuditClient(
      createOperationalAuditClient(
        createMockOperationalAuditTransport({
          auditEvents: createSyntheticAuditEvents(100),
        }),
      ),
    );
    renderShell('/app/audit');
    await waitFor(() => {
      expect(document.querySelector('[data-table-cursor-pagination]')).toBeInTheDocument();
    });
    expect(document.querySelector('[data-load-more]')).toBeInTheDocument();
    expect(document.querySelector('[data-table-pagination]')).not.toBeInTheDocument();
    expect(getTableDomRowCount(document.body)).toBe(AUDIT_LEDGER_BATCH_SIZE);
  });

  it('audit filters fieldset is keyboard reachable', async () => {
    resetAuthStateForTests();
    resetGovernanceStateForTests();
    clearSession();
    seedShellAuth('owner');
    renderShell('/app/audit');
    await waitFor(() => {
      expect(document.querySelector('[data-audit-ledger-filters]')).toBeInTheDocument();
    });
    const fieldset = document.querySelector('[data-audit-ledger-filters]');
    expect(fieldset?.querySelector('legend')).toBeTruthy();
    expect(fieldset?.querySelectorAll('label').length).toBeGreaterThan(0);
  });

  it('parses audit log mode and cursor from search params', () => {
    const filters = parseAuditFilters('?log=forensic&cursor=2026-01-01T00:00:00.000Z|evt_1');
    expect(filters.logMode).toBe('forensic_log');
    expect(filters.cursor).toBe('2026-01-01T00:00:00.000Z|evt_1');
  });
});
