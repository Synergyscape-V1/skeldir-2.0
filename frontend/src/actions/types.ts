import type { PolicyAuthorityState } from '../lib/types';

export type ActionOutcomeStatus =
  | 'success'
  | 'pending'
  | 'blocked_by_policy'
  | 'permission_denied'
  | 'scope_denied'
  | 'replay_rejected'
  | 'signature_failed'
  | 'artifact_unavailable'
  | 'audit_write_failed'
  | 'network_error'
  | 'timeout'
  | 'conflict_stale_object'
  | 'partial_failure'
  | 'subsystem_unsafe';

export type GovernedObjectType =
  | 'claim'
  | 'trust_envelope'
  | 'audit_event'
  | 'budget_simulation'
  | 'exception';

export type ExceptionActionKind =
  | 'acknowledge'
  | 'request_more_evidence'
  | 'mark_disputed'
  | 'suppress_similar'
  | 'create_proposal';

export type SignatureVerificationState =
  | 'valid'
  | 'invalid'
  | 'expired_key'
  | 'unknown_key'
  | 'revoked_key'
  | 'artifact_hash_mismatch'
  | 'semantic_truth_hash_mismatch'
  | 'network_error';

export interface GovernedActionOutcome {
  status: ActionOutcomeStatus;
  idempotencyKey: string;
  objectId: string;
  objectType: GovernedObjectType;
  tenantId: string;
  safeUserCopy: string;
  actionId?: string;
  policyAuthority?: PolicyAuthorityState;
  auditEventId?: string;
  artifactRef?: string | null;
  semanticTruthHash?: string | null;
  artifactHash?: string | null;
  signatureHash?: string | null;
  keyId?: string | null;
  signatureAlgorithm?: string | null;
  proposalId?: string | null;
  approvalState?: string | null;
  createdAt?: string;
  signatureVerification?: SignatureVerificationState;
}

export interface ClaimExportPreview {
  claimId: string;
  claimSource: string;
  claimedRevenueMinor: string;
  verifiedRevenueMinor: string;
  currencyCode: string;
  discrepancyClass: string;
  attributionModel: string;
  modelAssumption: string;
  causalStatus: string;
  confidenceSummary: string;
  benchmarkSummary: string;
  policyAuthority: PolicyAuthorityState;
  auditReference: string;
  incrementalityBoundaryCopy: string;
  authorityLegend: string[];
}

export interface TrustEnvelopeExportArtifact {
  schemaVersion: string;
  canonicalizationVersion: string;
  semanticTruthHash: string;
  artifactHash: string;
  signatureHash: string | null;
  keyId: string | null;
  signatureAlgorithm: string | null;
  createdAt: string;
  auditEventId: string;
  artifactRef: string;
  payloadBytes: number;
  oversize: boolean;
}

export interface AuditReconstructionPreview {
  eventIds: string[];
  hashChain: string[];
  redactionSummary: string[];
  previewBytes: number;
  oversize: boolean;
}

export interface ClaimsLedgerExportPreview {
  claimRefs: string[];
  totalCount: number;
  filterSummary: string[];
  previewBytes: number;
  oversize: boolean;
}

export interface BudgetProposalPreview {
  simulationId: string;
  assumptions: string[];
  verifiedRevenueBasisMinor: string;
  currencyCode: string;
  confidenceCaveat: string;
  benchmarkContext: string;
  policyAuthority: PolicyAuthorityState;
  riskCaveats: string[];
  projectedAllocation: Array<{ channel: string; shareBps: number }>;
}

export type ActionFlowPhase =
  | 'idle'
  | 'policy_blocked'
  | 'permission_denied'
  | 'scope_denied'
  | 'subsystem_unsafe'
  | 'confirmation_open'
  | 'pending'
  | 'success'
  | 'replay_rejected'
  | 'signature_failed'
  | 'artifact_unavailable'
  | 'audit_write_failed'
  | 'network_error'
  | 'timeout'
  | 'stale_object_conflict'
  | 'partial_failure';
