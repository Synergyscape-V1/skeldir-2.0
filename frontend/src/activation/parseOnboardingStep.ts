import type { OnboardingStep } from './types';

export function parseOnboardingStep(raw: string | undefined): OnboardingStep {
  if (!raw || !/^[1-6]$/.test(raw)) return 1;
  return parseInt(raw, 10) as OnboardingStep;
}
