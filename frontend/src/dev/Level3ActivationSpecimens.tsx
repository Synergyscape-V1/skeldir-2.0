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
  setWorkspaceConfirmed,
  setClaimSkipped,
  setPrivacyAcknowledged,
  setPrivacyConfirmed,
  unlockClaimStep,
  unlockPrivacyStep,
  setCurrentStep,
} from '../activation/activationStore';
import { AppShellRoutes } from '../app/routes/ShellRoutes';
import { PageSurface } from '../components/layout/PageSurface/PageSurface';
import { Typography } from '../components/layout/Typography/Typography';
import { OnboardingStepPanel } from '../components/onboarding/OnboardingStepPanel/OnboardingStepPanel';
import { TrustWorkspaceStep } from '../components/onboarding/TrustWorkspaceStep/TrustWorkspaceStep';
import { CommerceTruthStep } from '../components/onboarding/CommerceTruthStep/CommerceTruthStep';
import { ClaimSourcesStep } from '../components/onboarding/ClaimSourcesStep/ClaimSourcesStep';
import { PrivacyBoundaryStep } from '../components/onboarding/PrivacyBoundaryStep/PrivacyBoundaryStep';
import { OnboardingProgressRail } from '../components/onboarding/OnboardingProgressRail/OnboardingProgressRail';
import { OnboardingMobileProgressAccordion } from '../components/onboarding/OnboardingMobileProgressAccordion/OnboardingMobileProgressAccordion';
import { IntegrationsPage } from '../app/routes/ActivationRoutes';
import { CommerceSourceCard } from '../components/integration/CommerceSourceCard/CommerceSourceCard';
import { ClaimSourceCard } from '../components/integration/ClaimSourceCard/ClaimSourceCard';
import { ACTIVATION_COPY } from '../activation/copy';
import type { IntegrationSourceState } from '../integration/types';
import styles from '../app/authPages.module.css';

function SeedFixture({ fixture }: { fixture: string }) {
  useEffect(() => {
    resetAuthStateForTests();
    resetDefaultAuthClient();
    resetActivationStateForTests();
    resetDefaultIntegrationClient();

    if (!fixture.includes('guard')) {
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

    if (fixture.includes('step-1')) setCurrentStep(1);
    if (fixture.includes('step-2')) {
      setWorkspaceConfirmed('Acme RevOps');
      setCurrentStep(2);
    }
    if (fixture.includes('step-3')) {
      setWorkspaceConfirmed('Acme RevOps');
      unlockClaimStep();
      setCurrentStep(3);
    }
    if (fixture.includes('step-4')) {
      setWorkspaceConfirmed('Acme RevOps');
      unlockClaimStep();
      unlockPrivacyStep();
      setCurrentStep(4);
    }
    if (fixture.includes('privacy-confirmed')) {
      setPrivacyAcknowledged(true);
      setPrivacyConfirmed();
    }
    if (fixture.includes('claim-skip')) setClaimSkipped(true);
  }, [fixture]);
  return null;
}

function SpecimenBody({ fixture }: { fixture: string }) {
  if (fixture.startsWith('onboarding-step-1')) {
    return (
      <div className={styles.authPage}>
        <OnboardingProgressRail currentStep={1} maxUnlockedStep={1} />
        <TrustWorkspaceStep />
      </div>
    );
  }
  if (fixture.startsWith('onboarding-step-2')) {
    return (
      <div className={styles.authPage}>
        <OnboardingMobileProgressAccordion currentStep={2} maxUnlockedStep={2} />
        <CommerceTruthStep />
      </div>
    );
  }
  if (fixture.startsWith('onboarding-step-3')) return <ClaimSourcesStep />;
  if (fixture.startsWith('onboarding-step-4')) return <PrivacyBoundaryStep />;
  if (fixture.startsWith('integrations')) return <IntegrationsPage />;
  if (fixture.startsWith('commerce-card-connected')) {
    const state: IntegrationSourceState = {
      provider: 'shopify',
      kind: 'commerce',
      status: 'verification_ready',
      lastEventAt: new Date().toISOString(),
      verificationLabel: 'Signature verified',
    };
    return (
      <CommerceSourceCard state={state} onConnect={async () => {}} onRepair={async () => {}} />
    );
  }
  if (fixture.startsWith('claim-card-connected')) {
    const state: IntegrationSourceState = {
      provider: 'meta_ads',
      kind: 'claim',
      status: 'connected',
      lastClaimAt: new Date().toISOString(),
      reconciliationLabel: 'Pending commerce reconciliation',
    };
    return (
      <ClaimSourceCard state={state} onConnect={async () => {}} onRepair={async () => {}} />
    );
  }
  return (
    <OnboardingStepPanel heading={ACTIVATION_COPY.onboardingTitle}>
      <Typography variant="body">Unknown Level 3 specimen: {fixture}</Typography>
    </OnboardingStepPanel>
  );
}

function Level3SpecimenPage() {
  const [params] = useSearchParams();
  const fixture = params.get('fixture') ?? 'onboarding-step-1-default';

  if (fixture.startsWith('shell-onboarding')) {
    return (
      <>
        <SeedFixture fixture={fixture} />
        <MemoryRouter initialEntries={['/app/onboarding/step/1']}>
          <Routes>
            <Route path="/app/*" element={<AppShellRoutes />} />
          </Routes>
        </MemoryRouter>
      </>
    );
  }

  if (fixture.startsWith('shell-integrations')) {
    return (
      <>
        <SeedFixture fixture={fixture} />
        <MemoryRouter initialEntries={['/app/integrations']}>
          <Routes>
            <Route path="/app/*" element={<AppShellRoutes />} />
          </Routes>
        </MemoryRouter>
      </>
    );
  }

  return (
    <PageSurface>
      <SeedFixture fixture={fixture} />
      <SpecimenBody fixture={fixture} />
    </PageSurface>
  );
}

export function Level3ActivationSpecimens() {
  return (
    <MemoryRouter initialEntries={['/dev/level3-specimens?fixture=onboarding-step-1-default']}>
      <Routes>
        <Route path="/dev/level3-specimens" element={<Level3SpecimenPage />} />
      </Routes>
    </MemoryRouter>
  );
}
