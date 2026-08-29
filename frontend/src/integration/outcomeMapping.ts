import type { IntegrationOutcome } from './types';
import { INTEGRATION_COPY } from './copy';

export function mapIntegrationOutcomeToMessage(outcome: IntegrationOutcome): string {
  switch (outcome.kind) {
    case 'workspace_invalid':
      return 'Enter a valid workspace name before continuing.';
    case 'workspace_create_failed':
      return 'Workspace activation failed. No financial truth was changed.';
    case 'commerce_connection_failed':
    case 'claim_source_connection_failed':
      return INTEGRATION_COPY.actionFailed;
    case 'commerce_verification_failed':
      return 'Commerce verification failed. Deterministic evidence was not changed.';
    case 'privacy_confirmation_failed':
      return 'Privacy boundary confirmation failed. Durable trust surfaces remain blocked.';
    case 'permission_denied':
      return INTEGRATION_COPY.permissionDenied;
    case 'rate_limited':
      return INTEGRATION_COPY.rateLimited;
    case 'network_error':
      return INTEGRATION_COPY.networkError;
    case 'unknown_error':
      return 'An unexpected error occurred. No financial truth was changed.';
    default:
      return '';
  }
}
