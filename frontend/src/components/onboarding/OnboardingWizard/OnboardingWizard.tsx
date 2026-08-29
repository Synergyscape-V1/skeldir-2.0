import { useEffect, useState } from 'react';

import { Link, Navigate, useNavigate, useParams } from 'react-router-dom';

import { Typography } from '../../layout/Typography/Typography';

import { ACTIVATION_COPY } from '../../../activation/copy';

import {

  canAccessStep,

  setCurrentStep,

  setLevel6Complete,

  unlockClaimStep,

  unlockPrivacyStep,

} from '../../../activation/activationStore';

import { useActivationState } from '../../../activation/useActivationState';

import { useIntegrations } from '../../../integration/useIntegrations';

import { Level3RouteGuard } from '../Level3RouteGuard/Level3RouteGuard';

import { OnboardingFooterControls } from '../OnboardingFooterControls/OnboardingFooterControls';

import { OnboardingMobileProgressAccordion } from '../OnboardingMobileProgressAccordion/OnboardingMobileProgressAccordion';

import { OnboardingProgressRail } from '../OnboardingProgressRail/OnboardingProgressRail';

import { CommerceTruthStep } from '../CommerceTruthStep/CommerceTruthStep';

import { ClaimSourcesStep, isClaimStepComplete } from '../ClaimSourcesStep/ClaimSourcesStep';

import { PrivacyBoundaryStep, submitPrivacyStep } from '../PrivacyBoundaryStep/PrivacyBoundaryStep';

import { TrustWorkspaceStep, submitWorkspaceStep } from '../TrustWorkspaceStep/TrustWorkspaceStep';

import { GenerateFirstTrustEnvelopeStep } from '../GenerateFirstTrustEnvelopeStep/GenerateFirstTrustEnvelopeStep';

import { AddHumansOrAgentsStep } from '../AddHumansOrAgentsStep/AddHumansOrAgentsStep';

import { FIRST_TRUST_ENVELOPE_COPY } from '../../../firstTrustEnvelope/copy';

import styles from './OnboardingWizard.module.css';

import type { OnboardingStep } from '../../../activation/types';

import { parseOnboardingStep } from '../../../activation/parseOnboardingStep';



function parseStep(raw: string | undefined): OnboardingStep {

  return parseOnboardingStep(raw);

}



function renderStepPanel(step: OnboardingStep) {

  switch (step) {

    case 1:

      return <TrustWorkspaceStep />;

    case 2:

      return <CommerceTruthStep />;

    case 3:

      return <ClaimSourcesStep />;

    case 4:

      return <PrivacyBoundaryStep />;

    case 5:

      return <GenerateFirstTrustEnvelopeStep />;

    case 6:

      return <AddHumansOrAgentsStep />;

    default:

      return <TrustWorkspaceStep />;

  }

}



export function OnboardingWizard() {

  const { step: stepParam } = useParams<{ step: string }>();

  const navigate = useNavigate();

  const activation = useActivationState();

  const { commerceReady, integrations } = useIntegrations();

  const [continueLoading, setContinueLoading] = useState(false);

  const currentStep = parseStep(stepParam);



  useEffect(() => {

    setCurrentStep(currentStep);

  }, [currentStep]);



  if (stepParam && !canAccessStep(parseStep(stepParam))) {

    return <Navigate to={`/app/onboarding/step/${activation.maxUnlockedStep}`} replace />;

  }



  async function handleContinue() {

    setContinueLoading(true);

    try {

      if (currentStep === 1) {

        const ok = await submitWorkspaceStep(activation.workspaceName);

        if (ok) navigate('/app/onboarding/step/2');

        return;

      }

      if (currentStep === 2) {

        if (!commerceReady) return;

        unlockClaimStep();

        navigate('/app/onboarding/step/3');

        return;

      }

      if (currentStep === 3) {

        if (!isClaimStepComplete(integrations, activation.claimSkipped)) return;

        unlockPrivacyStep();

        navigate('/app/onboarding/step/4');

        return;

      }

      if (currentStep === 4) {

        const ok = await submitPrivacyStep(activation.privacyAcknowledged);

        if (ok) navigate('/app/onboarding/step/5');

        return;

      }

      if (currentStep === 5) {

        if (!activation.step5Complete) return;

        navigate('/app/onboarding/step/6');

        return;

      }

      if (currentStep === 6) {

        setLevel6Complete();

        navigate('/app/onboarding/complete');

      }

    } finally {

      setContinueLoading(false);

    }

  }



  function handleBack() {

    if (currentStep > 1) navigate(`/app/onboarding/step/${currentStep - 1}`);

  }



  function handleStepSelect(step: OnboardingStep) {

    if (canAccessStep(step)) navigate(`/app/onboarding/step/${step}`);

  }



  const continueBlockedReason =

    currentStep === 1 && activation.workspaceStatus === 'invalid'

      ? ACTIVATION_COPY.step1.continueBlocked

      : currentStep === 2 && !commerceReady

        ? ACTIVATION_COPY.step2.continueBlocked

        : currentStep === 3 &&

            !isClaimStepComplete(integrations, activation.claimSkipped) &&

            !activation.claimSkipped

          ? ACTIVATION_COPY.step3.skipAction

          : currentStep === 4 && !activation.privacyAcknowledged

            ? ACTIVATION_COPY.step4.continueBlocked

            : currentStep === 5 && !activation.step5Complete

              ? FIRST_TRUST_ENVELOPE_COPY.step5.generateDisabledReason

              : undefined;



  const continueDisabled =

    continueLoading ||

    (currentStep === 1 &&

      (activation.workspaceStatus === 'invalid' || activation.workspaceStatus === 'loading')) ||

    (currentStep === 2 && !commerceReady) ||

    (currentStep === 3 &&

      !isClaimStepComplete(integrations, activation.claimSkipped) &&

      !activation.claimSkipped) ||

    (currentStep === 4 && !activation.privacyAcknowledged) ||

    (currentStep === 5 && !activation.step5Complete);



  const continueLabel =

    currentStep === 4

      ? ACTIVATION_COPY.footer.continue

      : currentStep === 5

        ? FIRST_TRUST_ENVELOPE_COPY.step5.continueToStep6

        : currentStep === 6

          ? FIRST_TRUST_ENVELOPE_COPY.step6.completeLabel

          : ACTIVATION_COPY.footer.continue;



  return (

    <Level3RouteGuard mode="onboarding-step">

      <div className={styles.wizard} data-onboarding-wizard>

        <Typography variant="h1">{ACTIVATION_COPY.onboardingTitle}</Typography>

        <p>{ACTIVATION_COPY.onboardingDescription}</p>

        <OnboardingMobileProgressAccordion

          currentStep={currentStep}

          maxUnlockedStep={activation.maxUnlockedStep}

        />

        <div className={styles.layout}>

          <OnboardingProgressRail

            currentStep={currentStep}

            maxUnlockedStep={activation.maxUnlockedStep}

            onStepSelect={handleStepSelect}

          />

          <div className={styles.main}>{renderStepPanel(currentStep)}</div>

        </div>

        <OnboardingFooterControls

          showBack={currentStep > 1}

          onBack={handleBack}

          onContinue={() => void handleContinue()}

          backDisabled={continueLoading}

          continueDisabled={continueDisabled}

          continueLoading={continueLoading}

          blockedReason={continueBlockedReason}

          continueLabel={continueLabel}

        />

      </div>

    </Level3RouteGuard>

  );

}



export function OnboardingCompletePage() {

  const activation = useActivationState();

  if (!activation.level6Complete) {

    return <Navigate to={`/app/onboarding/step/${activation.maxUnlockedStep}`} replace />;

  }

  return (

    <section className={styles.completePanel} data-onboarding-complete>

      <Typography variant="h2">{ACTIVATION_COPY.completion.title}</Typography>

      <p>{ACTIVATION_COPY.completion.body}</p>

      <Link className={styles.actionLink} to="/app/integrations">

        {ACTIVATION_COPY.completion.integrationsLink}

      </Link>

    </section>

  );

}



export function OnboardingIndexRedirect() {

  return <Navigate to="/app/onboarding/step/1" replace />;

}


