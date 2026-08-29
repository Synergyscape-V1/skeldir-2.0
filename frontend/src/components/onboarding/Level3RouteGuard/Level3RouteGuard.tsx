import { Navigate, useParams } from 'react-router-dom';

import type { ReactNode } from 'react';

import { getActivationState, canAccessStep } from '../../../activation/activationStore';

import { parseOnboardingStep } from '../../../activation/parseOnboardingStep';

import { ACTIVATION_COPY } from '../../../activation/copy';

import { ErrorBanner } from '../../layout/ErrorBanner/ErrorBanner';



export interface Level3RouteGuardProps {

  children: ReactNode;

  mode: 'onboarding-step' | 'integrations';

}



export function Level3RouteGuard({ children, mode }: Level3RouteGuardProps) {

  // Read route params unconditionally so hook order is identical on every render
  // (React rules-of-hooks). useParams only reads router context, so calling it in
  // the 'integrations' mode is harmless; the branch below is unchanged.
  const { step } = useParams<{ step: string }>();

  if (mode === 'onboarding-step') {

    const parsed = parseOnboardingStep(step);

    const numericStep = parseInt(String(step ?? ''), 10);

    if (!step || numericStep < 1 || numericStep > 6 || String(numericStep) !== step) {

      return <Navigate to="/app/onboarding/step/1" replace />;

    }

    if (!canAccessStep(parsed)) {

      const { maxUnlockedStep } = getActivationState();

      return (

        <div role="alert">

          <ErrorBanner message={ACTIVATION_COPY.routeGuard.stepBlocked} />

          <Navigate to={`/app/onboarding/step/${maxUnlockedStep}`} replace />

        </div>

      );

    }

  }



  return <>{children}</>;

}


