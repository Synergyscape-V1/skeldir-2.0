import { ERROR_COPY } from '../lib/copy';
import type {
  AgentKeyCreateOutcome,
  AgentListOutcome,
  GovernanceError,
  PolicyOutcome,
  TeamOutcome,
} from './types';
import { GOVERNANCE_COPY } from './copy';

export function mapGovernanceError(error: GovernanceError): string {
  switch (error.kind) {
    case 'permission_denied':
      return GOVERNANCE_COPY.permissionDeniedBody;
    case 'network_failure':
      return ERROR_COPY.trustApiReadFailed;
    case 'rate_limited':
      return 'Too many requests. Wait and try again.';
    case 'validation_error':
      return error.message;
    case 'not_found':
      return 'Governance resource not found.';
    default:
      return ERROR_COPY.trustApiReadFailed;
  }
}

export function isGovernanceError(
  outcome: TeamOutcome | AgentListOutcome | AgentKeyCreateOutcome | PolicyOutcome,
): outcome is GovernanceError {
  return 'kind' in outcome && outcome.kind in {
    permission_denied: 1,
    network_failure: 1,
    rate_limited: 1,
    validation_error: 1,
    not_found: 1,
    unknown: 1,
  };
}
