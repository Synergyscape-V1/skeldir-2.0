import type { AuthorityClass, PolicyAuthorityState } from '../lib/types';

export type Step5PrerequisiteState =
  | 'locked_by_workspace'
  | 'locked_by_commerce_truth'
  | 'locked_by_privacy_boundary'
  | 'locked_by_policy_unavailable'
  | 'locked_by_audit_unavailable'
  | 'waiting_for_verified_commerce_event'
  | 'ready_to_generate';

export type GenerationUiPhase =
  | 'idle'
  | 'generation_queued'
  | 'generation_in_progress'
  | 'generation_succeeded'
  | 'generation_failed'
  | 'generation_already_exists'
  | 'generation_replay_rejected'
  | 'generation_permission_denied'
  | 'generation_rate_limited'
  | 'generation_network_error'
  | 'generation_schema_invalid'
  | 'generation_payload_oversized'
  | 'generation_payload_rejected'
  | 'generation_unknown_error';

export interface FirstTrustEnvelopeSummary {
  envelopeId: string;
  subjectRef: string;
  verifiedRevenueMinor: bigint;
  currencyCode: string;
  revenueAuthority: 'deterministic';
  attributionModel: string;
  attributionAuthority: 'deterministic';
  confidenceStatus: 'available' | 'unavailable' | 'delayed';
  confidenceAuthority?: AuthorityClass;
  confidenceReason?: string;
  confidenceMethodOrContext?: string;
  intervalLower?: number;
  intervalUpper?: number;
  credibleInterval?: string;
  uncertaintyBand?: string;
  qualitativeProbabilisticState?: string;
  sampleOrSourceContext?: string;
  benchmarkStatus?: 'unavailable' | 'suppressed';
  benchmarkReason?: string;
  policyAuthority: PolicyAuthorityState;
  auditEventId: string;
  generatedAt: string;
}

export type ReadinessOutcome =
  | { kind: 'first_envelope_ready' }
  | { kind: 'first_envelope_unavailable'; reason: Step5PrerequisiteState }
  | { kind: 'first_envelope_audit_unavailable'; message: string }
  | { kind: 'first_envelope_permission_denied' }
  | { kind: 'first_envelope_network_error' }
  | { kind: 'first_envelope_unknown_error'; message: string };

export type GenerationOutcome =
  | { kind: 'first_envelope_generation_started'; requestId: string }
  | { kind: 'first_envelope_generation_pending'; requestId: string }
  | { kind: 'first_envelope_generated'; envelope: FirstTrustEnvelopeSummary }
  | { kind: 'first_envelope_already_exists'; envelope: FirstTrustEnvelopeSummary }
  | { kind: 'first_envelope_replay_rejected'; message: string }
  | { kind: 'first_envelope_permission_denied' }
  | { kind: 'first_envelope_rate_limited' }
  | { kind: 'first_envelope_network_error' }
  | { kind: 'first_envelope_schema_invalid'; message: string }
  | { kind: 'first_envelope_payload_oversized'; message: string }
  | { kind: 'first_envelope_forbidden_payload_fields'; message: string }
  | { kind: 'first_envelope_audit_unavailable'; message: string }
  | { kind: 'first_envelope_unknown_error'; message: string };

export interface GenerationPrerequisites {
  workspaceConfirmed: boolean;
  commerceReady: boolean;
  privacyConfirmed: boolean;
  policyAvailable: boolean;
  auditSubstrateAvailable: boolean;
  verifiedCommerceEventAvailable: boolean;
}

export interface FirstTrustEnvelopeTransport {
  checkReadiness(
    tenantId: string,
    prerequisites: GenerationPrerequisites,
    signal?: AbortSignal,
  ): Promise<ReadinessOutcome>;
  generateFirstEnvelope(
    tenantId: string,
    idempotencyKey: string,
    signal?: AbortSignal,
  ): Promise<GenerationOutcome>;
  getExistingFirstEnvelope(
    tenantId: string,
    signal?: AbortSignal,
  ): Promise<FirstTrustEnvelopeSummary | null>;
}
