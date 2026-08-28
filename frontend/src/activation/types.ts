import type { FirstTrustEnvelopeSummary } from '../firstTrustEnvelope/types';
import type { GenerationUiPhase } from '../firstTrustEnvelope/types';

export type OnboardingStep = 1 | 2 | 3 | 4 | 5 | 6;

export type WorkspaceStepStatus =
  | 'loading'
  | 'invalid'
  | 'ready'
  | 'submitting'
  | 'success'
  | 'error';

export type PrivacyBoundaryStatus = 'unconfirmed' | 'confirming' | 'confirmed' | 'failed';

export interface ActivationState {
  currentStep: OnboardingStep;
  maxUnlockedStep: OnboardingStep;
  workspaceName: string;
  workspaceStatus: WorkspaceStepStatus;
  workspaceError?: string;
  workspaceConfirmed: boolean;
  integrationsLoaded: boolean;
  claimSkipped: boolean;
  claimSkipWarningVisible: boolean;
  privacyAcknowledged: boolean;
  privacyStatus: PrivacyBoundaryStatus;
  privacyError?: string;
  level3Complete: boolean;
  auditSubstrateAvailable: boolean;
  firstEnvelopeSummary: FirstTrustEnvelopeSummary | null;
  generationPhase: GenerationUiPhase;
  generationError?: string;
  generationSubmitLocked: boolean;
  step5Complete: boolean;
  level6Complete: boolean;
}

export const INITIAL_ACTIVATION_STATE: ActivationState = {
  currentStep: 1,
  maxUnlockedStep: 1,
  workspaceName: '',
  workspaceStatus: 'loading',
  workspaceConfirmed: false,
  integrationsLoaded: false,
  claimSkipped: false,
  claimSkipWarningVisible: false,
  privacyAcknowledged: false,
  privacyStatus: 'unconfirmed',
  level3Complete: false,
  auditSubstrateAvailable: false,
  firstEnvelopeSummary: null,
  generationPhase: 'idle',
  generationSubmitLocked: false,
  step5Complete: false,
  level6Complete: false,
};
