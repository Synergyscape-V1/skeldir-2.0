import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createMockSession, createMockTenant } from '../auth/authClient';
import {
  resolveSafeRedirect,
  LEVEL3_PERMITTED_ROUTES,
  LEVEL4_PLUS_BLOCKED_ROUTES,
} from '../auth/redirectGuard';
import {
  clearSession,
  establishTenant,
  resetAuthStateForTests,
  setBootstrapReady,
} from '../auth/sessionStore';
import {
  resetActivationStateForTests,
  setWorkspaceConfirmed,
  setClaimSkipped,
  setPrivacyAcknowledged,
  canAccessStep,
  getActivationState,
} from '../activation/activationStore';
import { runLevel1NegativeScopeScan } from '../audit/level1NegativeScopeScan';
import { runLevel2NegativeScopeScan } from '../audit/level2NegativeScopeScan';
import {
  assertLevel3ComponentsExist,
  assertLevel3RoutesExist,
  runLevel3NegativeScopeScan,
  runLevel3SabotageProbes,
} from '../audit/level3NegativeScopeScan';
import { runNegativeScopeScan } from '../audit/negativeScopeScan';
import { runPrivacyScan, runPrivacySabotageProbes } from '../audit/privacyScan';
import { runTokenAudit } from '../audit/tokenAudit';
import { AppShellRoutes } from '../app/routes/ShellRoutes';
import { ACTIVATION_COPY } from '../activation/copy';
import { INTEGRATION_COPY } from '../integration/copy';
import {
  createDefaultIntegrationStates,
  createIntegrationClient,
  createMockIntegrationTransport,
  isCommerceReady,
  resetDefaultIntegrationClient,
  setDefaultIntegrationClient,
} from '../integration/integrationClient';
import { IntegrationSourceCard } from '../components/integration/IntegrationSourceCard/IntegrationSourceCard';
import { PrivacyBoundaryAcknowledgement } from '../components/onboarding/PrivacyBoundaryAcknowledgement/PrivacyBoundaryAcknowledgement';
import {
  isChannelLogoPlaceholder,
  resolveChannelLogoSrc,
} from '../components/commandCenter/ChannelLogo/channelLogoMap';
import { CLAIM_PROVIDERS, COMMERCE_PROVIDERS } from '../integration/types';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

function renderShell(initialPath = '/app/onboarding/step/1') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/app/*" element={<AppShellRoutes />} />
        <Route path="/login" element={<div>Login page</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

function seedShellAuth() {
  establishTenant(createMockSession(), createMockTenant());
  setBootstrapReady();
}

describe('Level 3 Harness — Scope and regression', () => {
  beforeEach(() => {
    resetAuthStateForTests();
    resetActivationStateForTests();
    resetDefaultIntegrationClient();
    clearSession();
  });

  it('Level 0 negative scope still passes', () => {
    expect(runNegativeScopeScan().violations).toEqual([]);
  });

  it('Level 1 negative scope still passes', () => {
    expect(runLevel1NegativeScopeScan().violations).toEqual([]);
  });

  it('Level 2 negative scope still passes', () => {
    expect(runLevel2NegativeScopeScan().violations).toEqual([]);
  });

  it('Level 3 negative scope passes', () => {
    expect(runLevel3NegativeScopeScan().violations).toEqual([]);
  });

  it('privacy scan passes', () => {
    expect(runPrivacyScan().violations).toEqual([]);
  });

  it('Level 3 routes and components exist', () => {
    expect(assertLevel3RoutesExist()).toEqual({ ok: true, missing: [] });
    expect(assertLevel3ComponentsExist()).toEqual({ ok: true, missing: [] });
  });

  it('token audit passes including Level 3 surfaces', () => {
    expect(runTokenAudit().violations).toEqual([]);
  });
});

describe('Level 3 Harness — Activation routes', () => {
  beforeEach(() => {
    resetAuthStateForTests();
    resetActivationStateForTests();
    resetDefaultIntegrationClient();
    clearSession();
    setDefaultIntegrationClient(
      createIntegrationClient(createMockIntegrationTransport()),
    );
  });

  it('renders onboarding step 1 with session and tenant', async () => {
    seedShellAuth();
    renderShell('/app/onboarding/step/1');
    await waitFor(() => {
      expect(screen.getByText(ACTIVATION_COPY.step1.heading)).toBeInTheDocument();
    });
    expect(screen.getByText(ACTIVATION_COPY.step1.body)).toBeInTheDocument();
  });

  it('renders integrations page with commerce and claim groups', async () => {
    seedShellAuth();
    renderShell('/app/integrations');
    await waitFor(() => {
      expect(screen.getByText(INTEGRATION_COPY.commerceGroupTitle)).toBeInTheDocument();
    });
    expect(screen.getByText(INTEGRATION_COPY.claimGroupTitle)).toBeInTheDocument();
    expect(screen.getAllByText(INTEGRATION_COPY.commerceAuthorityCopy).length).toBeGreaterThan(0);
    expect(screen.getAllByText(INTEGRATION_COPY.claimSourceCopy).length).toBeGreaterThan(0);
  });

  it('redirect guard allows Level 3 permitted routes', () => {
    expect(LEVEL3_PERMITTED_ROUTES).toContain('/onboarding');
    expect(LEVEL3_PERMITTED_ROUTES).toContain('/integrations');
    expect(
      resolveSafeRedirect('/onboarding', { hasSession: true, hasTenant: true }, '/app'),
    ).toEqual({ ok: true, path: '/app/onboarding' });
  });

  it('redirect guard allows Level 7 claims route', () => {
    expect(resolveSafeRedirect('/claims', { hasSession: true, hasTenant: true }, '/app')).toEqual({
      ok: true,
      path: '/app/claims',
    });
  });
});

describe('Level 3 Harness — Workspace and commerce gating', () => {
  beforeEach(() => {
    resetActivationStateForTests();
  });

  it('step 2 blocked until workspace confirmed', () => {
    expect(canAccessStep(2)).toBe(false);
    setWorkspaceConfirmed('Acme RevOps');
    expect(canAccessStep(2)).toBe(true);
  });

  it('commerce ready requires connected commerce source', () => {
    const defaults = createDefaultIntegrationStates();
    expect(isCommerceReady(defaults)).toBe(false);
    const connected = defaults.map((entry) =>
      entry.provider === 'shopify'
        ? { ...entry, status: 'verification_ready' as const }
        : entry,
    );
    expect(isCommerceReady(connected)).toBe(true);
  });
});

describe('Level 3 Harness — Claim source semantics', () => {
  beforeEach(() => {
    resetActivationStateForTests();
  });

  it('claim skip enables step progression', () => {
    setWorkspaceConfirmed('Acme RevOps');
    setClaimSkipped(true);
    expect(getActivationState().claimSkipped).toBe(true);
    expect(getActivationState().claimSkipWarningVisible).toBe(true);
  });

  it('commerce card shows authority copy not claim copy', async () => {
    render(
      <IntegrationSourceCard
        state={{
          provider: 'shopify',
          kind: 'commerce',
          status: 'not_connected',
        }}
        authorityCopy={INTEGRATION_COPY.commerceAuthorityCopy}
        onConnect={async () => {}}
        onRepair={async () => {}}
        showLastEvent
        showVerification
      />,
    );
    expect(screen.getByText(INTEGRATION_COPY.commerceAuthorityCopy)).toBeInTheDocument();
    expect(screen.queryByText(INTEGRATION_COPY.claimSourceCopy)).not.toBeInTheDocument();
  });

  it('each commerce and named claim provider resolves a dedicated logo', () => {
    for (const provider of COMMERCE_PROVIDERS) {
      expect(isChannelLogoPlaceholder(provider)).toBe(false);
      expect(resolveChannelLogoSrc(provider)).toBeTruthy();
    }
    for (const provider of CLAIM_PROVIDERS) {
      if (provider === 'other') {
        expect(isChannelLogoPlaceholder(provider)).toBe(true);
        continue;
      }
      expect(isChannelLogoPlaceholder(provider)).toBe(false);
      expect(resolveChannelLogoSrc(provider)).toBeTruthy();
    }
  });

  it('integration source card renders provider logo beside title', () => {
    render(
      <IntegrationSourceCard
        state={{ provider: 'paypal', kind: 'commerce', status: 'not_connected' }}
        authorityCopy={INTEGRATION_COPY.commerceAuthorityCopy}
        onConnect={async () => {}}
        onRepair={async () => {}}
      />,
    );
    const logo = document.querySelector('[data-channel-logo="paypal"]');
    expect(logo).not.toBeNull();
    expect(logo?.getAttribute('data-channel-logo-placeholder')).toBeNull();
  });
});

describe('Level 3 Harness — Privacy boundary', () => {
  it('privacy acknowledgement control is labeled', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<PrivacyBoundaryAcknowledgement checked={false} onChange={onChange} />);
    const checkbox = screen.getByRole('checkbox');
    expect(checkbox).not.toBeChecked();
    await user.click(checkbox);
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it('privacy boundary copy includes minimization statement', () => {
    expect(ACTIVATION_COPY.step4.body).toContain('email addresses');
    expect(ACTIVATION_COPY.step4.body).toContain('IP addresses');
    expect(ACTIVATION_COPY.step4.body).toContain('raw headers');
  });

  it('privacy acknowledgement required state tracked', () => {
    resetActivationStateForTests();
    setPrivacyAcknowledged(false);
    expect(getActivationState().privacyAcknowledged).toBe(false);
    setPrivacyAcknowledged(true);
    expect(getActivationState().privacyAcknowledged).toBe(true);
  });
});

describe('Level 3 Harness — Integration state and actions', () => {
  it('unknown integration status renders error', () => {
    render(
      <IntegrationSourceCard
        state={{ provider: 'shopify', kind: 'commerce', status: 'unknown_status' }}
        authorityCopy={INTEGRATION_COPY.commerceAuthorityCopy}
        onConnect={async () => {}}
        onRepair={async () => {}}
      />,
    );
    expect(screen.getByText(INTEGRATION_COPY.unknownStatusError)).toBeInTheDocument();
  });

  it('integration client boundary isolates fetch from cards', () => {
    const cardSource = readFileSync(
      join(process.cwd(), 'src/components/integration/IntegrationSourceCard/IntegrationSourceCard.tsx'),
      'utf8',
    );
    expect(cardSource.includes('fetch(')).toBe(false);
  });
});

describe('Level 3 Harness — Sabotage controls', () => {
  it('detects injected claims route', () => {
    const sabotaged = '<Route path="/claims" element={<Claims />} />';
    const results = runLevel3SabotageProbes(sabotaged);
    expect(results.find((r) => r.name === 'claims-route')?.pass).toBe(true);
  });

  it('detects injected health strip', () => {
    const sabotaged = 'All systems operational';
    const results = runLevel3SabotageProbes(sabotaged);
    expect(results.find((r) => r.name === 'health-strip')?.pass).toBe(true);
  });

  it('privacy sabotage detects email in fixture', () => {
    const sample = 'const fixture = { email: "customer@example.com" };';
    const results = runPrivacySabotageProbes(sample);
    expect(results.find((r) => r.name === 'email-in-fixture')?.pass).toBe(true);
  });

  it('level3 scope scan flags premature TrustEnvelope surface', () => {
    const scan = runLevel3NegativeScopeScan();
    expect(scan.violations.some((v) => v.type === 'premature-trust-surface')).toBe(false);
    const fakeViolation = runLevel3SabotageProbes('TrustEnvelope detail');
    expect(fakeViolation.find((r) => r.name === 'trust-envelope-preview')?.pass).toBe(true);
  });
});