import type { FirstTrustEnvelopeSummary } from '../firstTrustEnvelope/types';
import type { GenerationUiPhase } from '../firstTrustEnvelope/types';
import type { ActivationState, OnboardingStep } from './types';
import { INITIAL_ACTIVATION_STATE } from './types';

let state: ActivationState = { ...INITIAL_ACTIVATION_STATE };
const listeners = new Set<(next: ActivationState) => void>();

export function getActivationState(): ActivationState {
  return state;
}

export function subscribeActivationState(listener: (next: ActivationState) => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function emit(next: ActivationState): void {
  state = next;
  for (const listener of listeners) listener(next);
}

function patch(partial: Partial<ActivationState>): void {
  emit({ ...state, ...partial });
}

export function resetActivationStateForTests(): void {
  emit({ ...INITIAL_ACTIVATION_STATE });
}

export function setCurrentStep(step: OnboardingStep): void {
  patch({ currentStep: step });
}

export function unlockStep(step: OnboardingStep): void {
  if (step > state.maxUnlockedStep) {
    patch({ maxUnlockedStep: step });
  }
}

export function setWorkspaceName(name: string): void {
  patch({
    workspaceName: name,
    workspaceStatus: name.trim().length >= 2 ? 'ready' : 'invalid',
    workspaceError: undefined,
  });
}

export function setWorkspaceLoading(): void {
  patch({ workspaceStatus: 'loading' });
}

export function setWorkspaceSubmitting(): void {
  patch({ workspaceStatus: 'submitting', workspaceError: undefined });
}

export function setWorkspaceConfirmed(name: string): void {
  patch({
    workspaceName: name,
    workspaceStatus: 'success',
    workspaceConfirmed: true,
    maxUnlockedStep: Math.max(state.maxUnlockedStep, 2) as OnboardingStep,
  });
}

export function setWorkspaceError(message: string): void {
  patch({ workspaceStatus: 'error', workspaceError: message, workspaceConfirmed: false });
}

export function setIntegrationsLoaded(): void {
  patch({ integrationsLoaded: true });
}

export function unlockCommerceStep(): void {
  unlockStep(2);
}

export function unlockClaimStep(): void {
  unlockStep(3);
}

export function unlockPrivacyStep(): void {
  unlockStep(4);
}

export function unlockTrustEnvelopeStep(): void {
  unlockStep(5);
}

export function unlockHumanAgentStep(): void {
  unlockStep(6);
}

export function setClaimSkipped(skipped: boolean): void {
  patch({
    claimSkipped: skipped,
    claimSkipWarningVisible: skipped,
    maxUnlockedStep: Math.max(state.maxUnlockedStep, 4) as OnboardingStep,
  });
}

export function setPrivacyAcknowledged(acknowledged: boolean): void {
  patch({
    privacyAcknowledged: acknowledged,
    privacyStatus: acknowledged ? state.privacyStatus : 'unconfirmed',
  });
}

export function setPrivacyConfirming(): void {
  patch({ privacyStatus: 'confirming', privacyError: undefined });
}

export function setPrivacyConfirmed(): void {
  patch({
    privacyAcknowledged: true,
    privacyStatus: 'confirmed',
    level3Complete: true,
    maxUnlockedStep: Math.max(state.maxUnlockedStep, 5) as OnboardingStep,
  });
}

export function setPrivacyFailed(message: string): void {
  patch({
    privacyStatus: 'failed',
    privacyError: message,
    level3Complete: false,
  });
}

export function setAuditSubstrateAvailable(available: boolean): void {
  patch({ auditSubstrateAvailable: available });
}

export function setGenerationPhase(phase: GenerationUiPhase): void {
  patch({ generationPhase: phase });
  if (phase === 'generation_succeeded' || phase === 'generation_already_exists') {
    patch({
      step5Complete: true,
      generationSubmitLocked: true,
      maxUnlockedStep: Math.max(state.maxUnlockedStep, 6) as OnboardingStep,
    });
  }
}

export function setFirstEnvelopeSummary(summary: FirstTrustEnvelopeSummary | null): void {
  patch({ firstEnvelopeSummary: summary });
}

export function setGenerationSubmitLocked(locked: boolean): void {
  patch({ generationSubmitLocked: locked });
}

export function setGenerationError(message: string | undefined): void {
  patch({ generationError: message });
}

export function setLevel6Complete(): void {
  patch({ level6Complete: true });
}

export function canAccessStep(step: OnboardingStep): boolean {
  if (step <= 4) return step <= state.maxUnlockedStep;
  if (step === 5) return state.maxUnlockedStep >= 5 && state.level3Complete;
  if (step === 6) {
    return state.maxUnlockedStep >= 6 && (state.step5Complete || state.generationPhase === 'generation_already_exists');
  }
  return false;
}

export function isStepComplete(step: OnboardingStep): boolean {
  switch (step) {
    case 1:
      return state.workspaceConfirmed;
    case 2:
      return state.maxUnlockedStep >= 3;
    case 3:
      return state.maxUnlockedStep >= 4 || state.claimSkipped;
    case 4:
      return state.level3Complete;
    case 5:
      return state.step5Complete;
    case 6:
      return state.level6Complete;
    default:
      return false;
  }
}

export function seedStep5ReadyForTests(): void {
  patch({
    workspaceConfirmed: true,
    workspaceStatus: 'success',
    privacyAcknowledged: true,
    privacyStatus: 'confirmed',
    level3Complete: true,
    auditSubstrateAvailable: true,
    maxUnlockedStep: 5,
    claimSkipped: true,
  });
}

export function seedStep6ReadyForTests(summary?: FirstTrustEnvelopeSummary): void {
  seedStep5ReadyForTests();
  patch({
    step5Complete: true,
    generationPhase: 'generation_succeeded',
    generationSubmitLocked: true,
    maxUnlockedStep: 6,
    firstEnvelopeSummary: summary ?? null,
  });
}
