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

  if (mode === 'onboarding-step') {

    const { step } = useParams<{ step: string }>();

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


