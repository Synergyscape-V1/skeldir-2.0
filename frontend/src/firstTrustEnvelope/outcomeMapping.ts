import { FIRST_TRUST_ENVELOPE_COPY } from './copy';
import type { GenerationOutcome, ReadinessOutcome } from './types';

export function mapReadinessOutcomeToMessage(outcome: ReadinessOutcome): string {
  switch (outcome.kind) {
    case 'first_envelope_ready':
      return '';
    case 'first_envelope_unavailable':
      switch (outcome.reason) {
        case 'locked_by_workspace':
          return FIRST_TRUST_ENVELOPE_COPY.step5.lockedWorkspace;
        case 'locked_by_commerce_truth':
          return FIRST_TRUST_ENVELOPE_COPY.step5.lockedCommerce;
        case 'locked_by_privacy_boundary':
          return FIRST_TRUST_ENVELOPE_COPY.step5.lockedPrivacy;
        case 'locked_by_policy_unavailable':
          return FIRST_TRUST_ENVELOPE_COPY.step5.lockedPolicy;
        case 'locked_by_audit_unavailable':
          return FIRST_TRUST_ENVELOPE_COPY.step5.lockedAudit;
        case 'waiting_for_verified_commerce_event':
          return FIRST_TRUST_ENVELOPE_COPY.step5.waitingEvent;
        default:
          return FIRST_TRUST_ENVELOPE_COPY.step5.generateDisabledReason;
      }
    case 'first_envelope_audit_unavailable':
      return outcome.message || FIRST_TRUST_ENVELOPE_COPY.step5.auditUnavailable;
    case 'first_envelope_permission_denied':
      return FIRST_TRUST_ENVELOPE_COPY.step5.permissionDenied;
    case 'first_envelope_network_error':
      return FIRST_TRUST_ENVELOPE_COPY.step5.networkError;
    case 'first_envelope_unknown_error':
      return outcome.message || FIRST_TRUST_ENVELOPE_COPY.step5.unknownError;
    default:
      return FIRST_TRUST_ENVELOPE_COPY.step5.unknownError;
  }
}

export function mapGenerationOutcomeToMessage(outcome: GenerationOutcome): string {
  switch (outcome.kind) {
    case 'first_envelope_generation_started':
      return FIRST_TRUST_ENVELOPE_COPY.step5.queued;
    case 'first_envelope_generation_pending':
      return FIRST_TRUST_ENVELOPE_COPY.step5.generating;
    case 'first_envelope_generated':
      return FIRST_TRUST_ENVELOPE_COPY.step5.success;
    case 'first_envelope_already_exists':
      return FIRST_TRUST_ENVELOPE_COPY.step5.alreadyExists;
    case 'first_envelope_replay_rejected':
      return outcome.message || FIRST_TRUST_ENVELOPE_COPY.step5.replayRejected;
    case 'first_envelope_permission_denied':
      return FIRST_TRUST_ENVELOPE_COPY.step5.permissionDenied;
    case 'first_envelope_rate_limited':
      return FIRST_TRUST_ENVELOPE_COPY.step5.rateLimited;
    case 'first_envelope_network_error':
      return FIRST_TRUST_ENVELOPE_COPY.step5.networkError;
    case 'first_envelope_schema_invalid':
      return outcome.message || FIRST_TRUST_ENVELOPE_COPY.step5.schemaInvalid;
    case 'first_envelope_payload_oversized':
      return outcome.message || FIRST_TRUST_ENVELOPE_COPY.step5.payloadOversized;
    case 'first_envelope_forbidden_payload_fields':
      return outcome.message || FIRST_TRUST_ENVELOPE_COPY.step5.payloadRejected;
    case 'first_envelope_audit_unavailable':
      return outcome.message || FIRST_TRUST_ENVELOPE_COPY.step5.auditUnavailable;
    case 'first_envelope_unknown_error':
      return outcome.message || FIRST_TRUST_ENVELOPE_COPY.step5.unknownError;
    default:
      return FIRST_TRUST_ENVELOPE_COPY.step5.unknownError;
  }
}

export function sanitizeBackendError(raw: string): string {
  if (/stack|trace|exception|sql|postgres|internal/i.test(raw)) {
    return FIRST_TRUST_ENVELOPE_COPY.step5.unknownError;
  }
  return raw;
}
