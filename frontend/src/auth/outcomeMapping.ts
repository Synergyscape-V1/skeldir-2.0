import type { AuthOutcome } from './types';
import { AUTH_COPY } from './copy';

export function mapAuthOutcomeToMessage(outcome: AuthOutcome): string {
  switch (outcome.kind) {
    case 'invalid_credentials':
      return AUTH_COPY.invalidCredentials;
    case 'email_not_business':
      return AUTH_COPY.emailNotBusiness;
    case 'tenant_already_exists':
      return AUTH_COPY.tenantAlreadyExists;
    case 'oauth_provider_unavailable':
      return AUTH_COPY.oauthUnavailable(outcome.provider);
    case 'oauth_callback_error':
      return AUTH_COPY.oauthCallbackError(outcome.provider);
    case 'rate_limited':
      return AUTH_COPY.rateLimited;
    case 'network_error':
      return AUTH_COPY.networkFailure;
    case 'session_expired':
      return AUTH_COPY.sessionExpired;
    case 'permission_denied':
      return AUTH_COPY.permissionDenied;
    case 'tenant_creation_pending':
      return AUTH_COPY.tenantCreationPending;
    case 'tenant_creation_failed':
      return AUTH_COPY.tenantCreationFailed;
    case 'unknown_error':
      return AUTH_COPY.unknownAuthState;
    default:
      return AUTH_COPY.unknownAuthState;
  }
}

export function mapAuthOutcomeToDetail(outcome: AuthOutcome): string | undefined {
  if (outcome.kind === 'rate_limited' && outcome.retryAfterSeconds) {
    return `Retry after ${outcome.retryAfterSeconds} seconds.`;
  }
  if (
    outcome.kind === 'unknown_error' ||
    outcome.kind === 'tenant_creation_failed' ||
    outcome.kind === 'email_not_business'
  ) {
    return outcome.detail;
  }
  return undefined;
}
