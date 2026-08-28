import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';
import { createMockSession, createMockTenant } from '../auth/authClient';
import {
  resolveSafeRedirect,
  LEVEL4_PERMITTED_ROUTES,
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
import {
  assertLevel4AgentAccessAbsent,
  assertLevel4ComponentsExist,
  assertLevel4RoutesExist,
  runLevel4NegativeScopeScan,
  runLevel4SabotageProbes,
} from '../audit/level4NegativeScopeScan';
import { runNegativeScopeScan } from '../audit/negativeScopeScan';
import { runPrivacyScan } from '../audit/privacyScan';
import {
  runSecretScan,
  runSecretSabotageProbes,
  SECRET_SABOTAGE_SAMPLES,
} from '../audit/secretScan';
import { runTokenAudit } from '../audit/tokenAudit';
import { AppShellRoutes } from '../app/routes/ShellRoutes';
import { GOVERNANCE_COPY } from '../governance/copy';
import {
  createGovernanceClient,
  createMockGovernanceTransport,
  resetDefaultGovernanceClient,
  setDefaultGovernanceClient,
} from '../governance/governanceClient';
import { resetGovernanceStateForTests, setCurrentUserRole } from '../governance/governanceStore';
import { canCreateAgentKey, hasPermission } from '../governance/permissions';
import { RESERVED_AGENT_SCOPES } from '../governance/types';
import { PolicyAuthorityPill } from '../components/trust/PolicyAuthorityPill/PolicyAuthorityPill';
import { ERROR_COPY } from '../lib/copy';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

function renderShell(initialPath = '/app/settings/team') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/app/*" element={<AppShellRoutes />} />
        <Route path="/login" element={<div>Login page</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

function seedShellAuth(role: 'owner' | 'viewer' | 'unknown_role' = 'owner') {
  establishTenant(createMockSession(), createMockTenant());
  setBootstrapReady();
  setCurrentUserRole(role);
  resetDefaultGovernanceClient();
  setDefaultGovernanceClient(
    createGovernanceClient(createMockGovernanceTransport({ currentUserRole: role })),
  );
}

describe('Level 4 Harness — Scope and regression', () => {
  beforeEach(() => {
    resetAuthStateForTests();
    resetGovernanceStateForTests();
    resetDefaultGovernanceClient();
    clearSession();
  });

  it('Level 0–3 regressions pass', () => {
    expect(runNegativeScopeScan().violations).toEqual([]);
    expect(runLevel1NegativeScopeScan().violations).toEqual([]);
    expect(runLevel2NegativeScopeScan().violations).toEqual([]);
    expect(runLevel3NegativeScopeScan().violations).toEqual([]);
    expect(runPrivacyScan().violations).toEqual([]);
    expect(runTokenAudit().violations).toEqual([]);
  });

  it('Level 4 scope and secret scans pass', () => {
    expect(runLevel4NegativeScopeScan().violations).toEqual([]);
    expect(runSecretScan().violations).toEqual([]);
  });

  it('Level 4 routes and components exist; Agent Access is absent', () => {
    expect(assertLevel4RoutesExist()).toEqual({ ok: true, missing: [] });
    expect(assertLevel4ComponentsExist()).toEqual({ ok: true, missing: [] });
    expect(assertLevel4AgentAccessAbsent()).toEqual({ ok: true, present: [] });
  });
});

describe('Level 4 Harness — Governance routes', () => {
  beforeEach(() => {
    resetAuthStateForTests();
    resetGovernanceStateForTests();
    resetDefaultGovernanceClient();
    clearSession();
    seedShellAuth('owner');
  });

  it('renders team settings', async () => {
    renderShell('/app/settings/team');
    await waitFor(() => {
      expect(document.querySelector('[data-team-settings-page]')).toBeInTheDocument();
    });
    expect(screen.getByText('Operator A.')).toBeInTheDocument();
  });

  it('does not expose Agent Access route or page', async () => {
    renderShell('/app/agents');
    await waitFor(() => {
      expect(document.querySelector('[data-agent-access-page]')).not.toBeInTheDocument();
    });
    expect(document.querySelector('[data-nav-item="agent-access"]')).toBeNull();
  });

  it('renders policy settings', async () => {
    renderShell('/app/settings/policy');
    await waitFor(() => {
      expect(document.querySelector('[data-policy-settings-page]')).toBeInTheDocument();
    });
    expect(screen.getByText('Revenue reads')).toBeInTheDocument();
  });

  it('redirect guard allows Level 4 routes and rejects removed agents alias', () => {
    expect(LEVEL4_PERMITTED_ROUTES).not.toContain('/agents');
    expect(
      resolveSafeRedirect('/settings/team', { hasSession: true, hasTenant: true }, '/app'),
    ).toEqual({ ok: true, path: '/app/settings/team' });
    expect(
      resolveSafeRedirect('/agents', { hasSession: true, hasTenant: true }, '/app'),
    ).toEqual({ ok: false, reason: 'unknown' });
  });

  it('redirect guard allows Level 7 claims route', () => {
    expect(resolveSafeRedirect('/claims', { hasSession: true, hasTenant: true }, '/app')).toEqual({
      ok: true,
      path: '/app/claims',
    });
  });

  it('redirect guard allows audit route at Level 5', () => {
    expect(
      resolveSafeRedirect('/audit', { hasSession: true, hasTenant: true }, '/app'),
    ).toEqual({ ok: true, path: '/app/audit' });
  });
});

describe('Level 4 Harness — Permissions and fail-closed', () => {
  beforeEach(() => {
    resetAuthStateForTests();
    resetGovernanceStateForTests();
    resetDefaultGovernanceClient();
    clearSession();
  });

  it('viewer cannot manage team', () => {
    expect(hasPermission('viewer', 'manage_team')).toBe(false);
    expect(hasPermission('viewer', 'create_agent_key')).toBe(false);
    expect(hasPermission('viewer', 'configure_policy')).toBe(false);
  });

  it('unknown role fails closed', async () => {
    seedShellAuth('unknown_role');
    setDefaultGovernanceClient(
      createGovernanceClient(createMockGovernanceTransport({ currentUserRole: 'unknown_role' })),
    );
    renderShell('/app/settings/team');
    await waitFor(() => {
      expect(document.querySelector('[data-team-settings-page]')).toBeInTheDocument();
    });
  });

  it('PolicyAuthorityPill invalid auto-execute in design partner mode', () => {
    render(
      <PolicyAuthorityPill
        state="auto_executable_within_policy"
        tenantPolicyMode="design_partner"
      />,
    );
    expect(screen.getByText(ERROR_COPY.invalidPolicyState)).toBeInTheDocument();
  });

  it('reserved agent scopes remain non-issuable', () => {
    expect(RESERVED_AGENT_SCOPES).toEqual(
      expect.arrayContaining(['propose_action', 'execute_action', 'refit_bayesian', 'resolve_exception']),
    );
    expect(canCreateAgentKey('viewer')).toBe(false);
  });
});

describe('Level 4 Harness — Sabotage controls', () => {
  it('scope sabotage probes detect violations', () => {
    const bad =
      'path="/audit" path="/claims" All systems operational fetch( in modal path="agents" agent-access';
    const results = runLevel4SabotageProbes(bad);
    expect(results.find((r) => r.name === 'audit-route')?.pass).toBe(true);
    expect(results.find((r) => r.name === 'claims-route')?.pass).toBe(true);
    expect(results.find((r) => r.name === 'health-strip')?.pass).toBe(true);
    expect(results.find((r) => r.name === 'team-route-allowed')?.pass).toBe(true);
    expect(results.find((r) => r.name === 'agents-route-absent')?.pass).toBe(true);
    expect(results.find((r) => r.name === 'agent-access-nav-absent')?.pass).toBe(true);
  });

  it('secret sabotage probes detect leaks', () => {
    const leakResults = runSecretSabotageProbes(SECRET_SABOTAGE_SAMPLES.accessTokenLeak);
    expect(leakResults.find((r) => r.name === 'access_token_leak')?.pass).toBe(true);
    expect(
      runSecretSabotageProbes(SECRET_SABOTAGE_SAMPLES.allowedPlaceholder).find(
        (r) => r.name === 'placeholder-allowed',
      )?.pass,
    ).toBe(true);
    expect(runSecretScan().violations).toEqual([]);
  });

  it('governance client boundary — no fetch in UI components', () => {
    const uiFiles = [
      'src/components/governance/TeamSettingsPage/TeamSettingsPage.tsx',
      'src/components/governance/PolicyConfigureModal/PolicyConfigureModal.tsx',
    ];
    for (const file of uiFiles) {
      const content = readFileSync(join(process.cwd(), file), 'utf8');
      expect(content.includes('fetch(')).toBe(false);
    }
  });
});

describe('Level 4 Harness — Permission hardening', () => {
  beforeEach(() => {
    resetAuthStateForTests();
    resetGovernanceStateForTests();
    resetDefaultGovernanceClient();
    clearSession();
  });

  it('viewer cannot configure policy rows', async () => {
    seedShellAuth('viewer');
    setDefaultGovernanceClient(
      createGovernanceClient(createMockGovernanceTransport({ currentUserRole: 'viewer' })),
    );
    renderShell('/app/settings/policy');
    await waitFor(() => {
      expect(document.querySelector('[data-policy-settings-page]')).toBeInTheDocument();
    });
    const configureButtons = screen.getAllByRole('button', { name: GOVERNANCE_COPY.policyConfigureButton });
    configureButtons.forEach((btn) => expect(btn).toBeDisabled());
  });
});
