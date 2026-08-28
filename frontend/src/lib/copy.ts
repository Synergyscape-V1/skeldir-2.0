/** Centralized Level 0 error and unavailable copy — H-UI-18 */

import { POLICY_AUTHORITY_EXPLANATION } from './policyAuthorityLabels';

export const ERROR_COPY = {
  trustApiReadFailed: 'Trust API read failed. No financial truth was changed.',
  permissionDenied: 'You do not have permission to view this trust object.',
  scopeDenied: 'This agent key does not include the required scope.',
  replayRejected: 'This request was rejected as a replay.',
  signatureFailure: 'Signature verification failed. Do not use this artifact externally.',
  invalidAuthorityState: 'Invalid authority state',
  invalidPolicyState: 'Invalid authority state returned.',
  tokenRegistryUnavailable: 'Token registry unavailable',
  tokenMissing: (name: string) => `Missing design token: ${name}`,
  missingRequiredProp: (prop: string) => `Missing required prop: ${prop}`,
  unknownEnum: (field: string, value: string) => `Unknown ${field}: ${value}`,
  configurationError: 'Configuration error',
} as const;

export const UNAVAILABLE_COPY = {
  default:
    'This field is unavailable. Skeldir will not fabricate confidence or benchmark values.',
  noConfidence:
    'Confidence is unavailable. Deterministic verification remains active.',
  noBenchmark: 'No defensible benchmark exists for this segment yet.',
  noCommerceTruth:
    'Connect a commerce or payment source to establish verified revenue truth.',
  noPlatformClaims:
    'No platform claims have arrived yet. Skeldir can verify commerce events now and compare claims after ad sources connect.',
  blockedSimulationTitle: 'Simulation unavailable',
  blockedSimulationBody: POLICY_AUTHORITY_EXPLANATION.blockedSparse,
} as const;

export const LOADING_COPY = {
  progress: 'Still loading verified trust state…',
  retry: 'Retry',
} as const;

export const ACTION_LOADING_COPY = {
  verifySignature: 'Verifying artifact against public key…',
} as const;

export const TOAST_COPY = {
  successExample: 'Artifact exported successfully.',
  errorExample: 'Export failed. No artifact was created.',
} as const;

export const HASH_COPY_ANNOUNCEMENTS = {
  semanticTruth: 'Semantic truth hash copied',
  artifact: 'Artifact hash copied',
  signature: 'Signature hash copied',
} as const;
