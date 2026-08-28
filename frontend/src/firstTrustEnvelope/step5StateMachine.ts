import type { SummaryValidationFailure } from './summaryValidation';
import type { GenerationPrerequisites, GenerationUiPhase, Step5PrerequisiteState } from './types';

export function resolveStep5PrerequisiteState(
  prerequisites: GenerationPrerequisites,
): Step5PrerequisiteState {
  if (!prerequisites.workspaceConfirmed) return 'locked_by_workspace';
  if (!prerequisites.commerceReady) return 'locked_by_commerce_truth';
  if (!prerequisites.privacyConfirmed) return 'locked_by_privacy_boundary';
  if (!prerequisites.policyAvailable) return 'locked_by_policy_unavailable';
  if (!prerequisites.auditSubstrateAvailable) return 'locked_by_audit_unavailable';
  if (!prerequisites.verifiedCommerceEventAvailable) return 'waiting_for_verified_commerce_event';
  return 'ready_to_generate';
}

export function canAttemptGeneration(prerequisiteState: Step5PrerequisiteState): boolean {
  return prerequisiteState === 'ready_to_generate';
}

export function isGenerationTerminal(phase: GenerationUiPhase): boolean {
  return (
    phase === 'generation_succeeded' ||
    phase === 'generation_already_exists' ||
    phase === 'generation_failed' ||
    phase === 'generation_replay_rejected' ||
    phase === 'generation_permission_denied' ||
    phase === 'generation_rate_limited' ||
    phase === 'generation_network_error' ||
    phase === 'generation_schema_invalid' ||
    phase === 'generation_payload_oversized' ||
    phase === 'generation_payload_rejected' ||
    phase === 'generation_unknown_error'
  );
}

export function mapValidationFailureToPhase(failure: SummaryValidationFailure): GenerationUiPhase {
  switch (failure) {
    case 'payload_oversized':
      return 'generation_payload_oversized';
    case 'forbidden_fields':
      return 'generation_payload_rejected';
    default:
      return 'generation_schema_invalid';
  }
}

export function isGenerationErrorPhase(phase: GenerationUiPhase): boolean {
  return (
    phase === 'generation_failed' ||
    phase === 'generation_replay_rejected' ||
    phase === 'generation_permission_denied' ||
    phase === 'generation_rate_limited' ||
    phase === 'generation_network_error' ||
    phase === 'generation_schema_invalid' ||
    phase === 'generation_payload_oversized' ||
    phase === 'generation_payload_rejected' ||
    phase === 'generation_unknown_error'
  );
}

export function mapGenerationOutcomeToPhase(outcomeKind: string): GenerationUiPhase {
  switch (outcomeKind) {
    case 'first_envelope_generation_started':
      return 'generation_queued';
    case 'first_envelope_generation_pending':
      return 'generation_in_progress';
    case 'first_envelope_generated':
      return 'generation_succeeded';
    case 'first_envelope_already_exists':
      return 'generation_already_exists';
    case 'first_envelope_replay_rejected':
      return 'generation_replay_rejected';
    case 'first_envelope_permission_denied':
      return 'generation_permission_denied';
    case 'first_envelope_rate_limited':
      return 'generation_rate_limited';
    case 'first_envelope_network_error':
      return 'generation_network_error';
    case 'first_envelope_schema_invalid':
      return 'generation_schema_invalid';
    case 'first_envelope_payload_oversized':
      return 'generation_payload_oversized';
    case 'first_envelope_forbidden_payload_fields':
      return 'generation_payload_rejected';
    default:
      return 'generation_unknown_error';
  }
}
