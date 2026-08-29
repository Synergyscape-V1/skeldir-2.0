import { ERROR_COPY } from '../lib/copy';
import { OPERATIONAL_AUDIT_COPY } from './copy';
import type { OperationalAuditError } from './types';

export { isOperationalAuditErrorOutcome as isOperationalAuditError } from './types';

export function mapOperationalAuditError(error: OperationalAuditError): string {
  switch (error.kind) {
    case 'permission_denied':
      return OPERATIONAL_AUDIT_COPY.permissionDeniedAudit;
    case 'network_failure':
      return ERROR_COPY.trustApiReadFailed;
    case 'rate_limited':
      return 'Too many requests. Wait and try again.';
    case 'not_found':
      return 'Operational audit resource not found.';
    default:
      return ERROR_COPY.trustApiReadFailed;
  }
}

export function healthOutcomeToState(outcome: import('./types').HealthOutcome): import('./types').SystemHealthState {
  switch (outcome.kind) {
    case 'health_operational':
      return 'operational';
    case 'health_confidence_degraded':
      return 'confidence_degraded';
    case 'health_api_paused':
      return 'api_paused';
    case 'health_integration_attention':
      return 'integration_attention';
    case 'health_unknown':
      return 'unknown';
    case 'health_loading':
      return 'loading';
    case 'health_fetch_failed':
      return 'fetch_failed';
    default:
      return 'unknown';
  }
}
