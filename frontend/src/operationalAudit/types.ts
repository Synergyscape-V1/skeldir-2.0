import type { PolicyAuthorityState } from '../lib/types';

export type ForensicChainVerification = 'intact' | 'review_required';

export type ForensicAuditEventType =
  | 'artifact_exported'
  | 'proposal_exported'
  | 'proposal_reviewed'
  | 'policy_decision_rendered'
  | 'exception_case_updated'
  | 'bayesian_fit_completed'
  | 'dispatch_executed'
  | 'dispatch_suppressed';

export type AuditEventType =
  | ForensicAuditEventType
  | 'trust_access'
  | 'trust_api_read'
  | 'simulation_read'
  | 'system_health'
  | 'integration_event'
  | 'task_failure'
  | 'policy_read'
  | 'artifact_read'
  | 'unknown';

export type AuditTier = 'tier_a' | 'tier_b' | 'unknown';

/** Mandatory ledger view — maps to physically separate backend tables. */
export type AuditLogMode = 'access_history' | 'forensic_log';

/** Business triage action categories for the forensic log filter bar. */
export type ForensicActionCategory = 'approved' | 'exported' | 'resolved' | 'system_action';

export type SignatureStatus = 'valid' | 'invalid' | 'unavailable' | 'unknown';

export type ArtifactAvailability = 'available' | 'unavailable' | 'corrupted' | 'access_denied';

export type DiagnosticIssueKind =
  | 'task_failure'
  | 'integration_degradation'
  | 'confidence_delayed'
  | 'trust_api_paused'
  | 'unknown';

export type SystemHealthState =
  | 'operational'
  | 'confidence_degraded'
  | 'api_paused'
  | 'integration_attention'
  | 'unknown'
  | 'loading'
  | 'fetch_failed';

export interface AuditEvent {
  eventId: string;
  occurredAt: string;
  eventType: AuditEventType;
  actorLabel: string;
  actorClientId?: string;
  actorKind?: 'human' | 'agent';
  agentLabel?: string;
  subjectLabel: string;
  businessSubjectLabel?: string;
  policyAuthority?: PolicyAuthorityState;
  chainVerification?: ForensicChainVerification;
  proposalRef?: string;
  tier: AuditTier;
  signatureStatus: SignatureStatus;
  artifactAvailability: ArtifactAvailability;
  envelopeRef?: string;
  claimRef?: string;
  /** Tier A — access history telemetry */
  endpoint?: string;
  httpStatusCode?: number;
  latencyMs?: number;
  /** Tier B — forensic register */
  idempotencyKey?: string;
  artifactHash?: string;
  previousArtifactHash?: string;
}

export interface AuditArtifact {
  eventId: string;
  eventType: AuditEventType;
  actorLabel: string;
  agentLabel?: string;
  subjectLabel: string;
  occurredAt: string;
  tier: AuditTier;
  signatureStatus: SignatureStatus;
  availability: ArtifactAvailability;
  semanticTruthHash?: string;
  artifactHash?: string;
  signatureHash?: string;
  previousStateHash?: string;
  previousArtifactHash?: string;
  idempotencyKey?: string;
  sourceSnapshotHash?: string;
  metadataJson?: string;
  reconstructionStatus?: 'intact' | 'broken' | 'unavailable';
  jsonPreview?: string;
  unavailableReason?: string;
}

export interface AuditFilters {
  logMode?: AuditLogMode;
  eventType?: AuditEventType | 'all';
  /** Business triage multi-select — empty/undefined means all action categories */
  actionCategories?: ForensicActionCategory[];
  actor?: string;
  agent?: string;
  envelopeId?: string;
  eventId?: string;
  claimId?: string;
  endpoint?: string;
  httpStatusCode?: number | 'all';
  tier?: AuditTier | 'all';
  dateFrom?: string;
  dateTo?: string;
  signatureStatus?: SignatureStatus | 'all';
  systemHealth?: boolean;
  pageSize?: number;
  /** @deprecated Audit ledger uses cursor pagination only */
  offset?: number;
  cursor?: string;
  openDrawer?: boolean;
}

export interface DiagnosticsQuery {
  pageSize?: number;
  offset?: number;
}

export interface DLQEvent {
  eventId: string;
  queueName: string;
  taskType: string;
  status: 'retryable' | 'not_retryable' | 'delayed';
  occurredAt: string;
  summary: string;
  issueKind: DiagnosticIssueKind;
}

export interface DiagnosticSummary {
  taskFailures: number;
  integrationIssues: number;
  confidenceDelayed: number;
  trustApiPaused: boolean;
}

export interface OperationalDiagnosticsPayload {
  summary: DiagnosticSummary;
  dlqEvents: DLQEvent[];
}

export type OperationalAuditErrorKind =
  | 'permission_denied'
  | 'network_failure'
  | 'rate_limited'
  | 'not_found'
  | 'unknown';

export interface OperationalAuditError {
  kind: OperationalAuditErrorKind;
  message?: string;
}

export type AuditLedgerOutcome =
  | {
      kind: 'audit_loaded';
      events: AuditEvent[];
      totalCount: number;
      pageSize: number;
      hasMore: boolean;
      nextCursor?: string;
      /** @deprecated offset pagination removed from audit ledger UI */
      offset?: number;
    }
  | { kind: 'audit_empty' }
  | { kind: 'audit_filtered_empty' }
  | OperationalAuditError;

export type AuditArtifactOutcome =
  | { kind: 'artifact_loaded'; artifact: AuditArtifact }
  | { kind: 'artifact_unavailable'; reason: string }
  | { kind: 'artifact_corrupted'; reason: string }
  | { kind: 'artifact_signature_invalid'; reason: string }
  | { kind: 'artifact_access_denied' }
  | OperationalAuditError;

export type DiagnosticsOutcome =
  | {
      kind: 'diagnostics_loaded';
      payload: OperationalDiagnosticsPayload;
      dlqEvents: DLQEvent[];
      totalCount: number;
      offset: number;
      pageSize: number;
      hasMore: boolean;
    }
  | { kind: 'diagnostics_empty' }
  | OperationalAuditError;

export type HealthOutcome =
  | { kind: 'health_operational' }
  | { kind: 'health_confidence_degraded' }
  | { kind: 'health_api_paused' }
  | { kind: 'health_integration_attention' }
  | { kind: 'health_unknown' }
  | { kind: 'health_loading' }
  | { kind: 'health_fetch_failed' }
  | OperationalAuditError;

export function isOperationalAuditErrorOutcome(
  outcome: AuditLedgerOutcome | AuditArtifactOutcome | DiagnosticsOutcome | HealthOutcome,
): outcome is OperationalAuditError {
  return (
    'kind' in outcome &&
    (outcome.kind === 'permission_denied' ||
      outcome.kind === 'network_failure' ||
      outcome.kind === 'rate_limited' ||
      outcome.kind === 'not_found' ||
      outcome.kind === 'unknown')
  );
}

export interface OperationalAuditTransport {
  listAuditEvents(
    tenantId: string,
    filters: AuditFilters,
    signal?: AbortSignal,
  ): Promise<AuditLedgerOutcome>;
  getAuditArtifact(
    tenantId: string,
    eventId: string,
    signal?: AbortSignal,
  ): Promise<AuditArtifactOutcome>;
  getDiagnostics(
    tenantId: string,
    query?: DiagnosticsQuery,
    signal?: AbortSignal,
  ): Promise<DiagnosticsOutcome>;
  getSystemHealth(tenantId: string, signal?: AbortSignal): Promise<HealthOutcome>;
}

export interface MockOperationalAuditOptions {
  currentUserRole?: 'owner' | 'admin' | 'manager' | 'viewer' | 'billing_only' | 'unknown_role';
  denyAudit?: boolean;
  denyDiagnostics?: boolean;
  denyArtifact?: boolean;
  healthState?: SystemHealthState;
  delayMs?: number;
  auditEvents?: AuditEvent[];
  diagnostics?: OperationalDiagnosticsPayload;
}
