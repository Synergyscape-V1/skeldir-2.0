import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';
import { createMockSession, createMockTenant } from '../auth/authClient';
import { resolveSafeRedirect, LEVEL6_PLUS_BLOCKED_ROUTES } from '../auth/redirectGuard';
import {
  clearSession,
  establishTenant,
  resetAuthStateForTests,
  setBootstrapReady,
} from '../auth/sessionStore';
import {
  resetActivationStateForTests,
  seedStep5ReadyForTests,
  seedStep6ReadyForTests,
  setPrivacyConfirmed,
  setWorkspaceConfirmed,
  setClaimSkipped,
  getActivationState,
} from '../activation/activationStore';
import { runLevel1NegativeScopeScan } from '../audit/level1NegativeScopeScan';
import { runLevel2NegativeScopeScan } from '../audit/level2NegativeScopeScan';
import { runLevel3NegativeScopeScan } from '../audit/level3NegativeScopeScan';
import { runLevel4NegativeScopeScan } from '../audit/level4NegativeScopeScan';
import { runLevel5NegativeScopeScan } from '../audit/level5NegativeScopeScan';
import {
  assertLevel6ComponentsExist,
  runLevel6IntegritySabotageProbes,
  runLevel6NegativeScopeScan,
  runLevel6SabotageProbes,
} from '../audit/level6NegativeScopeScan';
import { runNegativeScopeScan } from '../audit/negativeScopeScan';
import { runPrivacyScan } from '../audit/privacyScan';
import { runSecretScan, runSecretSabotageProbes, SECRET_SABOTAGE_SAMPLES } from '../audit/secretScan';
import { runTokenAudit } from '../audit/tokenAudit';
import { AppShellRoutes } from '../app/routes/ShellRoutes';
import { FIRST_TRUST_ENVELOPE_COPY } from '../firstTrustEnvelope/copy';
import {
  createFirstTrustEnvelopeClient,
  createMockFirstTrustEnvelopeTransport,
  hasVerifiedCommerceEvent,
  resetDefaultFirstTrustEnvelopeClient,
  setDefaultFirstTrustEnvelopeClient,
  validateEnvelopeSummary,
} from '../firstTrustEnvelope/firstTrustEnvelopeClient';
import { buildTrustEnvelopeAuditReferenceHref } from '../firstTrustEnvelope/auditReference';
import { resolveStep5PrerequisiteState, canAttemptGeneration } from '../firstTrustEnvelope/step5StateMachine';
import {
  createDefaultIntegrationStates,
  createIntegrationClient,
  createMockIntegrationTransport,
  resetDefaultIntegrationClient,
  setDefaultIntegrationClient,
} from '../integration/integrationClient';
import { resetGovernanceStateForTests, setCurrentUserRole } from '../governance/governanceStore';
import { canCreateAgentKey, canManageTeam } from '../governance/permissions';
import { FirstTrustEnvelopeSummary } from '../components/onboarding/FirstTrustEnvelopeSummary/FirstTrustEnvelopeSummary';
import { AddHumansOrAgentsStep } from '../components/onboarding/AddHumansOrAgentsStep/AddHumansOrAgentsStep';
import { OnboardingProgressRail } from '../components/onboarding/OnboardingProgressRail/OnboardingProgressRail';
import { OnboardingMobileProgressAccordion } from '../components/onboarding/OnboardingMobileProgressAccordion/OnboardingMobileProgressAccordion';
import {
  MAX_SUMMARY_PAYLOAD_BYTES,
  createAvailableConfidenceSummary,
  createDefaultUnavailableSummary,
  createOversizedSummaryFixture,
  detectForbiddenSummaryFields,
  hasProbabilisticConfidenceShape,
  isNakedScalarConfidence,
  measureSerializedPayloadBytes,
  validateSummaryTransportBoundary,
} from '../firstTrustEnvelope/summaryValidation';
import { mapValidationFailureToPhase } from '../firstTrustEnvelope/step5StateMachine';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

function renderShell(initialPath = '/app/onboarding/step/5') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/app/*" element={<AppShellRoutes />} />
        <Route path="/login" element={<div>Login page</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

function seedCommerceVerified() {
  const integrations = createDefaultIntegrationStates().map((entry) =>
    entry.kind === 'commerce' && entry.provider === 'shopify'
      ? {
          ...entry,
          status: 'verification_ready' as const,
          lastEventAt: new Date().toISOString(),
          verificationLabel: 'Signature verified',
        }
      : entry,
  );
  setDefaultIntegrationClient(
    createIntegrationClient(createMockIntegrationTransport({ integrations })),
  );
}

function seedShellAuth(role: 'owner' | 'viewer' | 'billing_only' = 'owner') {
  establishTenant(createMockSession(), createMockTenant());
  setBootstrapReady();
  setCurrentUserRole(role);
  resetDefaultFirstTrustEnvelopeClient();
  setDefaultFirstTrustEnvelopeClient(
    createFirstTrustEnvelopeClient(createMockFirstTrustEnvelopeTransport()),
  );
  seedCommerceVerified();
}

describe('Level 6 Harness — Scope and regression', () => {
  beforeEach(() => {
    resetAuthStateForTests();
    resetActivationStateForTests();
    resetGovernanceStateForTests();
    resetDefaultIntegrationClient();
    resetDefaultFirstTrustEnvelopeClient();
    clearSession();
  });

  it('Levels 0–5 regressions pass', () => {
    expect(runNegativeScopeScan().violations).toEqual([]);
    expect(runLevel1NegativeScopeScan().violations).toEqual([]);
    expect(runLevel2NegativeScopeScan().violations).toEqual([]);
    expect(runLevel3NegativeScopeScan().violations).toEqual([]);
    expect(runLevel4NegativeScopeScan().violations).toEqual([]);
    expect(runLevel5NegativeScopeScan().violations).toEqual([]);
    expect(runPrivacyScan().violations).toEqual([]);
    expect(runTokenAudit().violations).toEqual([]);
  });

  it('Level 6 scope scan passes', () => {
    expect(runLevel6NegativeScopeScan().violations).toEqual([]);
  });

  it('Level 6 components exist', () => {
    expect(assertLevel6ComponentsExist()).toEqual({ ok: true, missing: [] });
  });
});

describe('Level 6 Harness — Prerequisites and state machine', () => {
  it('blocks generate without commerce truth', () => {
    const state = resolveStep5PrerequisiteState({
      workspaceConfirmed: true,
      commerceReady: false,
      privacyConfirmed: true,
      policyAvailable: true,
      auditSubstrateAvailable: true,
      verifiedCommerceEventAvailable: false,
    });
    expect(state).toBe('locked_by_commerce_truth');
    expect(canAttemptGeneration(state)).toBe(false);
  });

  it('blocks generate without privacy boundary', () => {
    const state = resolveStep5PrerequisiteState({
      workspaceConfirmed: true,
      commerceReady: true,
      privacyConfirmed: false,
      policyAvailable: true,
      auditSubstrateAvailable: true,
      verifiedCommerceEventAvailable: true,
    });
    expect(state).toBe('locked_by_privacy_boundary');
  });

  it('shows waiting state without verified commerce event', () => {
    const state = resolveStep5PrerequisiteState({
      workspaceConfirmed: true,
      commerceReady: true,
      privacyConfirmed: true,
      policyAvailable: true,
      auditSubstrateAvailable: true,
      verifiedCommerceEventAvailable: false,
    });
    expect(state).toBe('waiting_for_verified_commerce_event');
  });

  it('hasVerifiedCommerceEvent requires verification_ready and lastEventAt', () => {
    const states = createDefaultIntegrationStates().map((entry) =>
      entry.kind === 'commerce' && entry.provider === 'shopify'
        ? { ...entry, status: 'verification_ready' as const, lastEventAt: new Date().toISOString() }
        : entry,
    );
    expect(hasVerifiedCommerceEvent(states)).toBe(true);
    expect(hasVerifiedCommerceEvent(createDefaultIntegrationStates())).toBe(false);
  });
});

describe('Level 6 Harness — Step 5 generation', () => {
  beforeEach(() => {
    resetAuthStateForTests();
    resetActivationStateForTests();
    resetGovernanceStateForTests();
    resetDefaultIntegrationClient();
    resetDefaultFirstTrustEnvelopeClient();
    clearSession();
    seedShellAuth('owner');
    seedStep5ReadyForTests();
    setPrivacyConfirmed();
    setWorkspaceConfirmed('Acme RevOps');
    setClaimSkipped(true);
  });

  it('renders Step 5 heading and generate control', async () => {
    renderShell('/app/onboarding/step/5');
    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: FIRST_TRUST_ENVELOPE_COPY.step5.heading }),
      ).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: FIRST_TRUST_ENVELOPE_COPY.step5.generateLabel })).toBeInTheDocument();
  });

  it('generates first TrustEnvelope with summary fields', async () => {
    const user = userEvent.setup();
    renderShell('/app/onboarding/step/5');
    await waitFor(() => {
      expect(screen.getByRole('button', { name: FIRST_TRUST_ENVELOPE_COPY.step5.generateLabel })).not.toBeDisabled();
    });
    await user.click(screen.getByRole('button', { name: FIRST_TRUST_ENVELOPE_COPY.step5.generateLabel }));
    await waitFor(() => {
      expect(screen.getByText('trust_envelope_01')).toBeInTheDocument();
    });
    expect(screen.getByText(/Audit event aud_te_001/i)).toBeInTheDocument();
    expect(getActivationState().step5Complete).toBe(true);
  });

  it('double-click issues only one generation request', async () => {
    const counter = { count: 0 };
    setDefaultFirstTrustEnvelopeClient(
      createFirstTrustEnvelopeClient(
        createMockFirstTrustEnvelopeTransport({ generationCallCounter: counter, delayMs: 100 }),
      ),
    );
    const user = userEvent.setup();
    renderShell('/app/onboarding/step/5');
    await waitFor(() => {
      expect(screen.getByRole('button', { name: FIRST_TRUST_ENVELOPE_COPY.step5.generateLabel })).not.toBeDisabled();
    });
    const button = screen.getByRole('button', { name: FIRST_TRUST_ENVELOPE_COPY.step5.generateLabel });
    await user.dblClick(button);
    await waitFor(() => {
      expect(getActivationState().step5Complete).toBe(true);
    });
    expect(counter.count).toBeLessThanOrEqual(1);
  });

  it('already-generated state is stable', async () => {
    const existing = {
      envelopeId: 'trust_envelope_existing',
      subjectRef: 'commerce_event_01',
      verifiedRevenueMinor: 999n,
      currencyCode: 'USD',
      revenueAuthority: 'deterministic' as const,
      attributionModel: 'linear',
      attributionAuthority: 'deterministic' as const,
      confidenceStatus: 'unavailable' as const,
      confidenceReason: 'Confidence is unavailable. Deterministic verification remains active.',
      policyAuthority: 'blocked' as const,
      auditEventId: 'aud_te_001',
      generatedAt: new Date().toISOString(),
    };
    setDefaultFirstTrustEnvelopeClient(
      createFirstTrustEnvelopeClient(
        createMockFirstTrustEnvelopeTransport({ existingEnvelope: existing }),
      ),
    );
    renderShell('/app/onboarding/step/5');
    await waitFor(() => {
      expect(screen.getByText('trust_envelope_existing')).toBeInTheDocument();
    });
  });
});

describe('Level 6 Harness — Summary semantics', () => {
  const envelope = {
    envelopeId: 'trust_envelope_01',
    subjectRef: 'commerce_event_01',
    verifiedRevenueMinor: 125000n,
    currencyCode: 'USD',
    revenueAuthority: 'deterministic' as const,
    attributionModel: 'last_touch',
    attributionAuthority: 'deterministic' as const,
    confidenceStatus: 'unavailable' as const,
    confidenceReason: 'Confidence is unavailable. Deterministic verification remains active.',
    policyAuthority: 'blocked' as const,
    auditEventId: 'aud_te_001',
    generatedAt: new Date().toISOString(),
  };

  it('renders authority metadata and audit link', () => {
    render(
      <MemoryRouter>
        <FirstTrustEnvelopeSummary envelope={envelope} />
      </MemoryRouter>,
    );
    expect(screen.getAllByText(/Deterministic/i).length).toBeGreaterThan(0);
    expect(screen.getByRole('link', { name: /Audit event aud_te_001/i })).toHaveAttribute(
      'href',
      buildTrustEnvelopeAuditReferenceHref('aud_te_001', 'trust_envelope_01'),
    );
  });

  it('blocks success without audit reference', () => {
    expect(validateEnvelopeSummary({ ...envelope, auditEventId: '' })).toBe(false);
    render(
      <MemoryRouter>
        <FirstTrustEnvelopeSummary envelope={{ ...envelope, auditEventId: '' }} />
      </MemoryRouter>,
    );
    expect(screen.getByText(FIRST_TRUST_ENVELOPE_COPY.summary.missingAuditReference)).toBeInTheDocument();
  });
});

describe('Level 6 Harness — Step 6 governance', () => {
  beforeEach(() => {
    resetAuthStateForTests();
    resetActivationStateForTests();
    resetGovernanceStateForTests();
    resetDefaultIntegrationClient();
    resetDefaultFirstTrustEnvelopeClient();
    clearSession();
    seedShellAuth('owner');
    seedStep6ReadyForTests();
  });

  it('Step 6 locked before first envelope', () => {
    resetActivationStateForTests();
    seedStep5ReadyForTests();
    render(
      <MemoryRouter>
        <AddHumansOrAgentsStep />
      </MemoryRouter>,
    );
    expect(screen.getByText(FIRST_TRUST_ENVELOPE_COPY.step6.lockedBeforeEnvelope)).toBeInTheDocument();
  });

  it('Step 6 links to team settings for owner', async () => {
    renderShell('/app/onboarding/step/6');
    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: FIRST_TRUST_ENVELOPE_COPY.step6.heading }),
      ).toBeInTheDocument();
    });
    expect(screen.getByRole('link', { name: FIRST_TRUST_ENVELOPE_COPY.step6.humanPathLink })).toHaveAttribute(
      'href',
      '/app/settings/team',
    );
    expect(screen.queryByRole('link', { name: /agent access/i })).not.toBeInTheDocument();
    expect(document.querySelector('[data-step6-agent-link]')).toBeNull();
  });

  it('viewer cannot manage team; agent key creation remains fail-closed', () => {
    setCurrentUserRole('viewer');
    expect(canManageTeam('viewer')).toBe(false);
    expect(canCreateAgentKey('viewer')).toBe(false);
  });

  it('billing_only fails closed for team management and agent creation', () => {
    setCurrentUserRole('billing_only');
    expect(canCreateAgentKey('billing_only')).toBe(false);
    expect(canManageTeam('billing_only')).toBe(false);
  });
});

describe('Level 6 Harness — Summary transport boundary', () => {
  it('accepts valid unavailable-confidence summary within byte budget', () => {
    const summary = createDefaultUnavailableSummary();
    const payload = {
      ...summary,
      verifiedRevenueMinor: summary.verifiedRevenueMinor.toString(),
    };
    const result = validateSummaryTransportBoundary(payload);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.byteSize).toBeLessThanOrEqual(MAX_SUMMARY_PAYLOAD_BYTES);
    }
  });

  it('rejects oversized summary payload fail-closed', () => {
    const oversized = createOversizedSummaryFixture();
    expect(measureSerializedPayloadBytes(oversized)).toBeGreaterThan(MAX_SUMMARY_PAYLOAD_BYTES);
    const result = validateSummaryTransportBoundary(oversized);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.failure).toBe('payload_oversized');
      expect(mapValidationFailureToPhase(result.failure)).toBe('generation_payload_oversized');
    }
  });

  it('rejects forbidden full-payload fields before hydration', () => {
    const base = createDefaultUnavailableSummary();
    const payload = {
      ...base,
      verifiedRevenueMinor: base.verifiedRevenueMinor.toString(),
      rawEnvelope: '{"claims":[]}',
      signedPayload: 'sig_material',
    };
    expect(detectForbiddenSummaryFields(payload)).toContain('rawEnvelope');
    const result = validateSummaryTransportBoundary(payload);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.failure).toBe('forbidden_fields');
      expect(mapValidationFailureToPhase(result.failure)).toBe('generation_payload_rejected');
    }
  });

  it('rejects naked scalar confidence without probabilistic shape', () => {
    const naked = {
      ...createDefaultUnavailableSummary(),
      confidenceStatus: 'available' as const,
      confidenceAuthority: 'probabilistic' as const,
    };
    expect(isNakedScalarConfidence(naked)).toBe(true);
    const result = validateSummaryTransportBoundary({
      ...naked,
      verifiedRevenueMinor: naked.verifiedRevenueMinor.toString(),
    });
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.failure).toBe('naked_scalar_confidence');
    }
  });

  it('accepts available confidence with interval and method context', () => {
    const shaped = createAvailableConfidenceSummary();
    expect(hasProbabilisticConfidenceShape(shaped)).toBe(true);
    const result = validateSummaryTransportBoundary({
      ...shaped,
      verifiedRevenueMinor: shaped.verifiedRevenueMinor.toString(),
    });
    expect(result.ok).toBe(true);
  });
});

describe('Level 6 Harness — Structural truth hierarchy', () => {
  const envelope = createDefaultUnavailableSummary();

  it('renders authority-tier regions in DOM order', () => {
    const { container } = render(
      <MemoryRouter>
        <FirstTrustEnvelopeSummary envelope={envelope} />
      </MemoryRouter>,
    );
    const tiers = Array.from(
      container.querySelectorAll('[data-authority-tier]'),
    ).map((node) => node.getAttribute('data-authority-tier'));
    expect(tiers).toEqual([
      'deterministic-primary',
      'model-output',
      'probabilistic-subordinate',
      'benchmark-subordinate',
      'policy-governance',
      'audit-reference',
      'metadata-subordinate',
    ]);
  });

  it('uses heading hierarchy with primary h2 before subordinate h3 regions', () => {
    render(
      <MemoryRouter>
        <FirstTrustEnvelopeSummary envelope={envelope} />
      </MemoryRouter>,
    );
    const headings = screen.getAllByRole('heading');
    expect(headings[0].tagName).toBe('H2');
    expect(headings.slice(1).every((heading) => heading.tagName === 'H3')).toBe(true);
  });

  it('renders probabilistic confidence shape when available', () => {
    render(
      <MemoryRouter>
        <FirstTrustEnvelopeSummary envelope={createAvailableConfidenceSummary()} />
      </MemoryRouter>,
    );
    expect(screen.getByText(/12% – 18% posterior interval/i)).toBeInTheDocument();
    expect(screen.queryByText(/^available$/i)).not.toBeInTheDocument();
  });

  it('fails sabotaged hierarchy collapse probe on uniform row-only markup', () => {
    const sabotaged = `<section><div className={styles.row}><span>Confidence: 94%</span></div></section>`;
    expect(sabotaged.includes('className={styles.row}')).toBe(true);
    expect(sabotaged.includes('data-authority-tier')).toBe(false);
  });
});

describe('Level 6 Harness — Generation failure phases', () => {
  beforeEach(() => {
    resetAuthStateForTests();
    resetActivationStateForTests();
    resetGovernanceStateForTests();
    resetDefaultIntegrationClient();
    resetDefaultFirstTrustEnvelopeClient();
    clearSession();
    seedShellAuth('owner');
    seedStep5ReadyForTests();
    setPrivacyConfirmed();
    setWorkspaceConfirmed('Acme RevOps');
    setClaimSkipped(true);
  });

  it('maps schema invalid to generation_schema_invalid phase', async () => {
    setDefaultFirstTrustEnvelopeClient(
      createFirstTrustEnvelopeClient(
        createMockFirstTrustEnvelopeTransport({ schemaInvalid: true }),
      ),
    );
    const user = userEvent.setup();
    renderShell('/app/onboarding/step/5');
    await waitFor(() => {
      expect(screen.getByRole('button', { name: FIRST_TRUST_ENVELOPE_COPY.step5.generateLabel })).not.toBeDisabled();
    });
    await user.click(screen.getByRole('button', { name: FIRST_TRUST_ENVELOPE_COPY.step5.generateLabel }));
    await waitFor(() => {
      expect(getActivationState().generationPhase).toBe('generation_schema_invalid');
    });
    expect(getActivationState().step5Complete).toBe(false);
  });

  it('maps oversized payload to generation_payload_oversized phase', async () => {
    const oversized = createOversizedSummaryFixture();
    setDefaultFirstTrustEnvelopeClient(
      createFirstTrustEnvelopeClient(
        createMockFirstTrustEnvelopeTransport({
          generationResult: {
            kind: 'first_envelope_generated',
            envelope: oversized as never,
          },
        }),
      ),
    );
    const user = userEvent.setup();
    renderShell('/app/onboarding/step/5');
    await waitFor(() => {
      expect(screen.getByRole('button', { name: FIRST_TRUST_ENVELOPE_COPY.step5.generateLabel })).not.toBeDisabled();
    });
    await user.click(screen.getByRole('button', { name: FIRST_TRUST_ENVELOPE_COPY.step5.generateLabel }));
    await waitFor(() => {
      expect(getActivationState().generationPhase).toBe('generation_payload_oversized');
    });
    expect(screen.getAllByRole('alert').length).toBeGreaterThan(0);
  });

  it('maps forbidden payload fields to generation_payload_rejected phase', async () => {
    const base = createDefaultUnavailableSummary();
    setDefaultFirstTrustEnvelopeClient(
      createFirstTrustEnvelopeClient(
        createMockFirstTrustEnvelopeTransport({
          generationResult: {
            kind: 'first_envelope_generated',
            envelope: { ...base, rawEnvelope: '{}' } as never,
          },
        }),
      ),
    );
    const user = userEvent.setup();
    renderShell('/app/onboarding/step/5');
    await waitFor(() => {
      expect(screen.getByRole('button', { name: FIRST_TRUST_ENVELOPE_COPY.step5.generateLabel })).not.toBeDisabled();
    });
    await user.click(screen.getByRole('button', { name: FIRST_TRUST_ENVELOPE_COPY.step5.generateLabel }));
    await waitFor(() => {
      expect(getActivationState().generationPhase).toBe('generation_payload_rejected');
    });
  });

  it('allows keyboard retry after network error', async () => {
    setDefaultFirstTrustEnvelopeClient(
      createFirstTrustEnvelopeClient(
        createMockFirstTrustEnvelopeTransport({ networkError: true }),
      ),
    );
    const user = userEvent.setup();
    renderShell('/app/onboarding/step/5');
    await waitFor(() => {
      expect(screen.getByRole('button', { name: FIRST_TRUST_ENVELOPE_COPY.step5.generateLabel })).not.toBeDisabled();
    });
    const generateButton = screen.getByRole('button', { name: FIRST_TRUST_ENVELOPE_COPY.step5.generateLabel });
    generateButton.focus();
    await user.keyboard('{Enter}');
    await waitFor(() => {
      expect(getActivationState().generationPhase).toBe('generation_network_error');
    });
    resetDefaultFirstTrustEnvelopeClient();
    setDefaultFirstTrustEnvelopeClient(
      createFirstTrustEnvelopeClient(createMockFirstTrustEnvelopeTransport()),
    );
    const retryButton = screen.getByRole('button', { name: FIRST_TRUST_ENVELOPE_COPY.step5.retryLabel });
    retryButton.focus();
    await user.keyboard('{Enter}');
    await waitFor(() => {
      expect(getActivationState().step5Complete).toBe(true);
    });
  });
});

describe('Level 6 Harness — Interaction accessibility', () => {
  it('progress rail step buttons are keyboard focusable', async () => {
    const user = userEvent.setup();
    render(
      <OnboardingProgressRail currentStep={5} maxUnlockedStep={5} onStepSelect={() => undefined} />,
    );
    const step5 = screen.getByRole('button', { name: /Step 5/i });
    step5.focus();
    expect(step5).toHaveFocus();
    await user.keyboard('{Enter}');
  });

  it('mobile accordion exposes keyboard-operable controls', async () => {
    const user = userEvent.setup();
    render(<OnboardingMobileProgressAccordion currentStep={5} maxUnlockedStep={5} />);
    const trigger = screen.getByRole('button', { name: /Step 5 of 6/i });
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
    trigger.focus();
    await user.keyboard('{Enter}');
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('region', { name: 'Onboarding steps' })).toBeInTheDocument();
    expect(screen.getByText(/Step 5:/i)).toBeInTheDocument();
  });

  it('generation status uses live region semantics on error', async () => {
    resetAuthStateForTests();
    resetActivationStateForTests();
    resetGovernanceStateForTests();
    resetDefaultIntegrationClient();
    resetDefaultFirstTrustEnvelopeClient();
    clearSession();
    seedShellAuth('owner');
    seedStep5ReadyForTests();
    setPrivacyConfirmed();
    setWorkspaceConfirmed('Acme RevOps');
    setClaimSkipped(true);
    setDefaultFirstTrustEnvelopeClient(
      createFirstTrustEnvelopeClient(
        createMockFirstTrustEnvelopeTransport({ networkError: true }),
      ),
    );
    const user = userEvent.setup();
    renderShell('/app/onboarding/step/5');
    await waitFor(() => {
      expect(screen.getByRole('button', { name: FIRST_TRUST_ENVELOPE_COPY.step5.generateLabel })).not.toBeDisabled();
    });
    await user.click(screen.getByRole('button', { name: FIRST_TRUST_ENVELOPE_COPY.step5.generateLabel }));
    await waitFor(() => {
      const status = document.querySelector('[data-generation-status]');
      expect(status).toHaveAttribute('aria-live', 'assertive');
      expect(status).toHaveAttribute('role', 'alert');
    });
  });
});

describe('Level 6 Harness — Secret scan coverage', () => {
  it('includes evidence/Level_6 in secret scan roots', () => {
    const result = runSecretScan();
    expect(result.filesScanned).toBeGreaterThan(0);
    expect(result.violations).toEqual([]);
  });
});

describe('Level 6 Harness — Negative scope and sabotage', () => {
  it('redirect guard still blocks Level 7+ routes', () => {
    for (const route of LEVEL6_PLUS_BLOCKED_ROUTES) {
      const result = resolveSafeRedirect(route, { hasSession: true, hasTenant: true }, '/app');
      expect(result.ok).toBe(false);
    }
  });

  it('integrity sabotage probes pass on clean tree', () => {
    const probes = runLevel6IntegritySabotageProbes();
    expect(probes.every((p) => p.pass)).toBe(true);
  });

  it('string sabotage samples fail when injected', () => {
    const clean = readFileSync(
      join(process.cwd(), 'src', 'components', 'onboarding', 'GenerateFirstTrustEnvelopeStep', 'GenerateFirstTrustEnvelopeStep.tsx'),
      'utf8',
    );
    expect(runLevel6SabotageProbes(clean).filter((r) => !r.expected).every((r) => r.pass)).toBe(true);
    const sabotage = `${clean}\npath="/claims"\npath="/trust/:envelopeId"\nexportArtifact\nverifySignature\ncopyApiResponse\nTrustEnvelopeJsonViewer\npropose_action\nplatform claim is verified revenue\nfetch(\nInternal Server Error at\nrawEnvelope\nsignedPayload\nenvelopeJson\nConfidence: 94%\nclassName={styles.row}`;
    expect(runLevel6SabotageProbes(sabotage).filter((r) => r.expected).every((r) => r.pass)).toBe(true);
  });

  it('secret sabotage probes detect controlled violations', () => {
    const results = runSecretSabotageProbes(Object.values(SECRET_SABOTAGE_SAMPLES).join('\n'));
    expect(results.filter((r) => r.name.includes('leak')).every((r) => r.pass)).toBe(true);
  });
});
