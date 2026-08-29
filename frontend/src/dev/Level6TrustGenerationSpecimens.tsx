import { MemoryRouter, Route, Routes, useSearchParams } from 'react-router-dom';
import { useEffect } from 'react';
import {
  createMockIntegrationTransport,
  createDefaultIntegrationStates,
  createIntegrationClient,
  resetDefaultIntegrationClient,
  setDefaultIntegrationClient,
} from '../integration/integrationClient';
import {
  createMockSession,
  createMockTenant,
  resetDefaultAuthClient,
} from '../auth/authClient';
import {
  establishTenant,
  resetAuthStateForTests,
  setBootstrapReady,
} from '../auth/sessionStore';
import {
  resetActivationStateForTests,
  seedStep5ReadyForTests,
  seedStep6ReadyForTests,
  setCurrentStep,
  setPrivacyConfirmed,
  setWorkspaceConfirmed,
  setClaimSkipped,
  setGenerationPhase,
  setFirstEnvelopeSummary,
  setAuditSubstrateAvailable,
} from '../activation/activationStore';
import {
  createFirstTrustEnvelopeClient,
  createMockFirstTrustEnvelopeTransport,
  resetDefaultFirstTrustEnvelopeClient,
  setDefaultFirstTrustEnvelopeClient,
} from '../firstTrustEnvelope/firstTrustEnvelopeClient';
import { resetGovernanceStateForTests, setCurrentUserRole } from '../governance/governanceStore';
import { AppShellRoutes } from '../app/routes/ShellRoutes';
import { FirstTrustEnvelopeSummary } from '../components/onboarding/FirstTrustEnvelopeSummary/FirstTrustEnvelopeSummary';
import { GenerateFirstTrustEnvelopeStep } from '../components/onboarding/GenerateFirstTrustEnvelopeStep/GenerateFirstTrustEnvelopeStep';
import { createAvailableConfidenceSummary } from '../firstTrustEnvelope/summaryValidation';
import { AddHumansOrAgentsStep } from '../components/onboarding/AddHumansOrAgentsStep/AddHumansOrAgentsStep';
import { OnboardingProgressRail } from '../components/onboarding/OnboardingProgressRail/OnboardingProgressRail';
import { OnboardingMobileProgressAccordion } from '../components/onboarding/OnboardingMobileProgressAccordion/OnboardingMobileProgressAccordion';
import { PageSurface } from '../components/layout/PageSurface/PageSurface';
import { Typography } from '../components/layout/Typography/Typography';
import styles from '../app/authPages.module.css';

const sampleEnvelope = {
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
  generatedAt: '2026-06-28T12:00:00.000Z',
};

function SeedFixture({ fixture }: { fixture: string }) {
  useEffect(() => {
    resetAuthStateForTests();
    resetDefaultAuthClient();
    resetActivationStateForTests();
    resetDefaultIntegrationClient();
    resetDefaultFirstTrustEnvelopeClient();
    resetGovernanceStateForTests();

    if (!fixture.includes('no-session')) {
      establishTenant(createMockSession(), createMockTenant());
      setBootstrapReady();
    }

    const commerceConnected = createDefaultIntegrationStates().map((entry) =>
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
      createIntegrationClient(createMockIntegrationTransport({ integrations: commerceConnected })),
    );

    setDefaultFirstTrustEnvelopeClient(
      createFirstTrustEnvelopeClient(createMockFirstTrustEnvelopeTransport()),
    );

    if (fixture.includes('viewer')) setCurrentUserRole('viewer');
    else setCurrentUserRole('owner');

    if (fixture.includes('step-5')) {
      seedStep5ReadyForTests();
      setPrivacyConfirmed();
      setWorkspaceConfirmed('Acme RevOps');
      setClaimSkipped(true);
      setAuditSubstrateAvailable(true);
      setCurrentStep(5);
    }

    if (fixture.includes('step-6')) {
      seedStep6ReadyForTests(sampleEnvelope);
      setFirstEnvelopeSummary(sampleEnvelope);
      setGenerationPhase('generation_succeeded');
      setCurrentStep(6);
    }

    if (fixture.includes('waiting-event')) {
      const noEvent = createDefaultIntegrationStates().map((entry) =>
        entry.kind === 'commerce' && entry.provider === 'shopify'
          ? { ...entry, status: 'connected' as const, lastEventAt: undefined }
          : entry,
      );
      setDefaultIntegrationClient(
        createIntegrationClient(createMockIntegrationTransport({ integrations: noEvent })),
      );
    }

    if (fixture.includes('locked-commerce')) {
      setDefaultIntegrationClient(
        createIntegrationClient(createMockIntegrationTransport()),
      );
      resetActivationStateForTests();
      setWorkspaceConfirmed('Acme RevOps');
      setPrivacyConfirmed();
      setCurrentStep(5);
    }

    if (fixture.includes('generation-success')) {
      seedStep5ReadyForTests();
      setFirstEnvelopeSummary(sampleEnvelope);
      setGenerationPhase('generation_succeeded');
    }

    if (fixture.includes('generation-failed')) {
      seedStep5ReadyForTests();
      setGenerationPhase('generation_network_error');
    }

    if (fixture.includes('already-generated')) {
      seedStep5ReadyForTests();
      setFirstEnvelopeSummary(sampleEnvelope);
      setGenerationPhase('generation_already_exists');
      setDefaultFirstTrustEnvelopeClient(
        createFirstTrustEnvelopeClient(
          createMockFirstTrustEnvelopeTransport({ existingEnvelope: sampleEnvelope }),
        ),
      );
    }

    if (fixture.includes('permission-denied')) {
      setCurrentUserRole('billing_only');
    }

    if (fixture.includes('payload-oversized')) {
      seedStep5ReadyForTests();
      setGenerationPhase('generation_payload_oversized');
      setPrivacyConfirmed();
      setWorkspaceConfirmed('Acme RevOps');
      setClaimSkipped(true);
    }

    if (fixture.includes('schema-invalid')) {
      seedStep5ReadyForTests();
      setGenerationPhase('generation_schema_invalid');
      setPrivacyConfirmed();
      setWorkspaceConfirmed('Acme RevOps');
      setClaimSkipped(true);
    }

    if (fixture.includes('confidence-available')) {
      seedStep5ReadyForTests();
      const shaped = createAvailableConfidenceSummary();
      setFirstEnvelopeSummary(shaped);
      setGenerationPhase('generation_succeeded');
    }
  }, [fixture]);

  return null;
}

function SpecimenBody({ fixture }: { fixture: string }) {
  if (fixture.includes('shell-step-5') || fixture.includes('shell-step-6')) {
    return <AppShellRoutes />;
  }

  if (fixture.includes('confidence-available')) {
    return (
      <PageSurface>
        <Typography variant="h1">Level 6 — confidence shape specimen</Typography>
        <FirstTrustEnvelopeSummary envelope={createAvailableConfidenceSummary()} />
      </PageSurface>
    );
  }

  return (
    <PageSurface>
      <Typography variant="h1">Level 6 specimens</Typography>
      <OnboardingMobileProgressAccordion
        currentStep={fixture.includes('step-6') ? 6 : 5}
        maxUnlockedStep={fixture.includes('step-6') ? 6 : 5}
      />
      <div className={styles.specimenLayout}>
        <OnboardingProgressRail
          currentStep={fixture.includes('step-6') ? 6 : 5}
          maxUnlockedStep={fixture.includes('step-6') ? 6 : 5}
        />
        <div>
          {fixture.includes('step-6') ? <AddHumansOrAgentsStep /> : <GenerateFirstTrustEnvelopeStep />}
        </div>
      </div>
    </PageSurface>
  );
}

function Level6SpecimenRouter() {
  const [params] = useSearchParams();
  const fixture = params.get('fixture') ?? 'step-5-ready';

  return (
    <div className={styles.page}>
      <SeedFixture fixture={fixture} />
      <SpecimenBody fixture={fixture} />
    </div>
  );
}

export function Level6TrustGenerationSpecimens() {
  return (
    <MemoryRouter initialEntries={['/dev/level6-specimens?fixture=step-5-ready']}>
      <Routes>
        <Route path="/dev/level6-specimens" element={<Level6SpecimenRouter />} />
        <Route path="/app/*" element={<AppShellRoutes />} />
      </Routes>
    </MemoryRouter>
  );
}
