import { getCurrentUserRole } from '../governance/governanceStore';
import {
  canOpenAuditArtifact,
  canViewAudit,
  canViewDiagnostics,
} from './permissions';
import type {
  AuditArtifact,
  AuditArtifactOutcome,
  AuditEvent,
  AuditFilters,
  AuditLedgerOutcome,
  DiagnosticsOutcome,
  DiagnosticsQuery,
  HealthOutcome,
  MockOperationalAuditOptions,
  OperationalAuditTransport,
  OperationalDiagnosticsPayload,
  SystemHealthState,
} from './types';
import { OPERATIONAL_AUDIT_COPY } from './copy';
import { auditLogModeToTier, resolveAuditLogMode } from './auditLogMode';
import {
  actorSearchHaystack,
  eventMatchesForensicCategories,
  matchesPartialRef,
} from './forensicBusinessTriage';
import {
  AUDIT_LEDGER_BATCH_SIZE,
  sliceCursorPage,
  slicePage,
  sortAuditEventsNewestFirst,
} from './pagination';
import {
  buildSyntheticTrustEnvelopeAuditEventId,
  buildSyntheticTrustEnvelopeId,
  DEFAULT_SYNTHETIC_TRUST_ENVELOPE_COUNT,
} from '../trustIndex/trustEnvelopeAuditIdentity';

let defaultClient: ReturnType<typeof createOperationalAuditClient> | null = null;

export interface OperationalAuditClient {
  listAuditEvents(
    tenantId: string,
    filters: AuditFilters,
    signal?: AbortSignal,
  ): Promise<AuditLedgerOutcome>;
  getAuditArtifact(tenantId: string, eventId: string, signal?: AbortSignal): Promise<AuditArtifactOutcome>;
  getDiagnostics(tenantId: string, query?: DiagnosticsQuery, signal?: AbortSignal): Promise<DiagnosticsOutcome>;
  getSystemHealth(tenantId: string, signal?: AbortSignal): Promise<HealthOutcome>;
}

export function createOperationalAuditClient(
  transport: OperationalAuditTransport,
): OperationalAuditClient {
  return {
    listAuditEvents: (tenantId, filters, signal) =>
      transport.listAuditEvents(tenantId, filters, signal),
    getAuditArtifact: (tenantId, eventId, signal) =>
      transport.getAuditArtifact(tenantId, eventId, signal),
    getDiagnostics: (tenantId, query, signal) => transport.getDiagnostics(tenantId, query, signal),
    getSystemHealth: (tenantId, signal) => transport.getSystemHealth(tenantId, signal),
  };
}

function defaultTrustEnvelopeForensicEvents(now: number): AuditEvent[] {
  return Array.from({ length: DEFAULT_SYNTHETIC_TRUST_ENVELOPE_COUNT }, (_, index) => {
    const envelopeId = buildSyntheticTrustEnvelopeId(index);
    const eventId = buildSyntheticTrustEnvelopeAuditEventId(index);
    const artifactHash = `artifact_hash_${eventId}`;

    return {
      eventId,
      occurredAt: new Date(now - index * 7_200_000).toISOString(),
      eventType: 'artifact_exported',
      actorLabel: 'Skeldir Trust Service',
      actorKind: 'agent',
      actorClientId: 'svc_trust_envelope_builder',
      subjectLabel: envelopeId,
      businessSubjectLabel: `TrustEnvelope ${envelopeId}`,
      policyAuthority: 'blocked',
      chainVerification: 'intact',
      tier: 'tier_b',
      signatureStatus: 'valid',
      artifactAvailability: 'available',
      envelopeRef: envelopeId,
      idempotencyKey: `idem_${eventId}`,
      artifactHash,
    };
  });
}

function defaultAuditEvents(): AuditEvent[] {
  const now = Date.now();
  const forensicChain = [
    {
      eventId: 'evt_artifact_export_01',
      artifactHash: 'artifact_hash_evt_01',
      previousArtifactHash: 'artifact_hash_evt_02',
    },
    {
      eventId: 'evt_policy_decision_01',
      artifactHash: 'artifact_hash_evt_02',
      previousArtifactHash: 'artifact_hash_evt_03',
    },
    {
      eventId: 'evt_exception_update_01',
      artifactHash: 'artifact_hash_evt_03',
      previousArtifactHash: 'artifact_hash_evt_04',
    },
    {
      eventId: 'evt_bayesian_fit_01',
      artifactHash: 'artifact_hash_evt_04',
      previousArtifactHash: undefined,
    },
  ] as const;

  return [
    ...defaultTrustEnvelopeForensicEvents(now),
    {
      eventId: forensicChain[0].eventId,
      occurredAt: new Date(now - 540_000).toISOString(),
      eventType: 'artifact_exported',
      actorLabel: 'jane@agency.com',
      actorKind: 'human',
      actorClientId: 'usr_a1b2c3d4-e5f6-7890-abcd-ef1234567890',
      subjectLabel: 'env_te_9f2a8b1c',
      businessSubjectLabel: 'Trust Envelope: ord_8f9a',
      policyAuthority: 'blocked',
      chainVerification: 'intact',
      tier: 'tier_b',
      signatureStatus: 'valid',
      artifactAvailability: 'available',
      envelopeRef: 'env_te_9f2a8b1c',
      claimRef: 'ORD-8821',
      idempotencyKey: 'idem_evt_artifact_export_01',
      artifactHash: forensicChain[0].artifactHash,
      previousArtifactHash: forensicChain[0].previousArtifactHash,
    },
    {
      eventId: forensicChain[1].eventId,
      occurredAt: new Date(now - 1_380_000).toISOString(),
      eventType: 'policy_decision_rendered',
      actorLabel: 'finance@acme.example',
      actorKind: 'human',
      actorClientId: 'usr_b2c3d4e5-f6a7-8901-bcde-f12345678901',
      subjectLabel: 'env_te_4c7d1e9a',
      businessSubjectLabel: 'Policy decision: env_te_4c7d1e9a',
      policyAuthority: 'approval_required',
      chainVerification: 'intact',
      tier: 'tier_b',
      signatureStatus: 'valid',
      artifactAvailability: 'available',
      envelopeRef: 'env_te_4c7d1e9a',
      idempotencyKey: 'idem_evt_policy_decision_01',
      artifactHash: forensicChain[1].artifactHash,
      previousArtifactHash: forensicChain[1].previousArtifactHash,
    },
    {
      eventId: forensicChain[2].eventId,
      occurredAt: new Date(now - 1_680_000).toISOString(),
      eventType: 'exception_case_updated',
      actorLabel: 'ops@acme.example',
      actorKind: 'human',
      actorClientId: 'usr_c3d4e5f6-a7b8-9012-cdef-123456789012',
      subjectLabel: 'exc_queue_88fa',
      businessSubjectLabel: 'Exception case: exc_queue_88fa',
      policyAuthority: 'blocked',
      chainVerification: 'intact',
      tier: 'tier_b',
      signatureStatus: 'valid',
      artifactAvailability: 'available',
      envelopeRef: 'env_te_4c7d1e9a',
      idempotencyKey: 'idem_evt_exception_update_01',
      artifactHash: forensicChain[2].artifactHash,
      previousArtifactHash: forensicChain[2].previousArtifactHash,
    },
    {
      eventId: forensicChain[3].eventId,
      occurredAt: new Date(now - 2_760_000).toISOString(),
      eventType: 'proposal_exported',
      actorLabel: 'Skeldir-MCP',
      actorKind: 'agent',
      actorClientId: 'agt_mcp_client_7e21d0f4',
      agentLabel: 'Skeldir-MCP',
      subjectLabel: 'sim_0002',
      businessSubjectLabel: 'Budget Proposal #BP-2841',
      proposalRef: 'sim_0002',
      policyAuthority: 'proposal_required',
      chainVerification: 'intact',
      tier: 'tier_b',
      signatureStatus: 'valid',
      artifactAvailability: 'available',
      envelopeRef: 'env_te_2b9f6e31',
      idempotencyKey: 'idem_evt_bayesian_fit_01',
      artifactHash: forensicChain[3].artifactHash,
      previousArtifactHash: forensicChain[3].previousArtifactHash,
    },
    {
      eventId: 'aud_tier_a_read_001',
      occurredAt: new Date(now - 300_000).toISOString(),
      eventType: 'trust_api_read',
      actorLabel: 'viewer@acme.example',
      actorClientId: 'usr_viewer_001',
      subjectLabel: 'env_te_9f2a8b1c',
      tier: 'tier_a',
      signatureStatus: 'unavailable',
      artifactAvailability: 'unavailable',
      envelopeRef: 'env_te_9f2a8b1c',
      endpoint: '/v1/trust/envelopes/env_te_9f2a8b1c',
      httpStatusCode: 200,
      latencyMs: 42,
    },
    {
      eventId: 'aud_001',
      occurredAt: new Date(now - 3600_000).toISOString(),
      eventType: 'system_health',
      actorLabel: 'actor_01',
      subjectLabel: 'tenant_event_subject',
      tier: 'tier_a',
      signatureStatus: 'valid',
      artifactAvailability: 'available',
      endpoint: '/v1/system/health',
      httpStatusCode: 200,
      latencyMs: 18,
    },
    {
      eventId: 'aud_002',
      occurredAt: new Date(now - 7200_000).toISOString(),
      eventType: 'trust_access',
      actorLabel: 'actor_01',
      agentLabel: 'agent_01',
      subjectLabel: 'env_ref_placeholder',
      tier: 'tier_a',
      signatureStatus: 'valid',
      artifactAvailability: 'available',
      envelopeRef: 'env_ref_placeholder',
      endpoint: '/app/trust/env_ref_placeholder',
      httpStatusCode: 200,
      latencyMs: 95,
    },
    {
      eventId: 'aud_003',
      occurredAt: new Date(now - 86400_000).toISOString(),
      eventType: 'artifact_read',
      actorLabel: 'actor_02',
      subjectLabel: 'tenant_event_subject',
      tier: 'tier_b',
      signatureStatus: 'invalid',
      artifactAvailability: 'corrupted',
      idempotencyKey: 'idem_aud_003',
      artifactHash: 'artifact_hash_broken',
      previousArtifactHash: 'artifact_hash_mismatch',
    },
    {
      eventId: 'aud_004',
      occurredAt: new Date(now - 172800_000).toISOString(),
      eventType: 'integration_event',
      actorLabel: 'actor_01',
      subjectLabel: 'integration_subject',
      tier: 'tier_a',
      signatureStatus: 'unavailable',
      artifactAvailability: 'unavailable',
      endpoint: '/v1/integrations/shopify/events',
      httpStatusCode: 503,
      latencyMs: 1200,
    },
    {
      eventId: 'aud_005',
      occurredAt: new Date(now - 259200_000).toISOString(),
      eventType: 'unknown',
      actorLabel: 'actor_01',
      subjectLabel: 'tenant_event_subject',
      tier: 'unknown',
      signatureStatus: 'unknown',
      artifactAvailability: 'available',
    },
    {
      eventId: 'aud_006',
      occurredAt: new Date(now - 432000_000).toISOString(),
      eventType: 'artifact_read',
      actorLabel: 'actor_02',
      subjectLabel: 'tenant_event_subject',
      tier: 'tier_b',
      signatureStatus: 'invalid',
      artifactAvailability: 'available',
      idempotencyKey: 'idem_aud_006',
      artifactHash: 'artifact_hash_aud_006',
      previousArtifactHash: 'artifact_hash_evt_01',
      chainVerification: 'review_required',
      businessSubjectLabel: 'Artifact read: tenant_event_subject',
    },
  ];
}

export function createSyntheticAuditEvents(count: number): AuditEvent[] {
  return Array.from({ length: count }, (_, index) => ({
    eventId: `aud_syn_${String(index).padStart(6, '0')}`,
    occurredAt: new Date(Date.now() - index * 60_000).toISOString(),
    eventType: 'trust_access' as const,
    actorLabel: 'actor_01',
    subjectLabel: 'tenant_event_subject',
    tier: 'tier_a' as const,
    signatureStatus: 'valid' as const,
    artifactAvailability: 'available' as const,
    endpoint: '/v1/trust/envelopes',
    httpStatusCode: 200,
    latencyMs: 30 + (index % 40),
    envelopeRef: `env_syn_${index}`,
  }));
}

export function createSyntheticDLQEvents(count: number): import('./types').DLQEvent[] {
  return Array.from({ length: count }, (_, index) => ({
    eventId: `dlq_syn_${String(index).padStart(6, '0')}`,
    queueName: 'b23_match_engine',
    taskType: 'match_dispatch',
    status: 'retryable' as const,
    occurredAt: new Date(Date.now() - index * 120_000).toISOString(),
    summary: `Synthetic queue event ${index}`,
    issueKind: 'task_failure' as const,
  }));
}

function defaultDiagnostics(): OperationalDiagnosticsPayload {
  return {
    summary: {
      taskFailures: 1,
      integrationIssues: 1,
      confidenceDelayed: 1,
      trustApiPaused: false,
    },
    dlqEvents: [
      {
        eventId: 'dlq_001',
        queueName: 'b23_match_engine',
        taskType: 'match_dispatch',
        status: 'retryable',
        occurredAt: new Date(Date.now() - 1800_000).toISOString(),
        summary: 'Match task retry scheduled after transient worker timeout.',
        issueKind: 'task_failure',
      },
      {
        eventId: 'dlq_002',
        queueName: 'integration_repair',
        taskType: 'integration_health',
        status: 'not_retryable',
        occurredAt: new Date(Date.now() - 5400_000).toISOString(),
        summary: 'Commerce integration requires manual repair context review.',
        issueKind: 'integration_degradation',
      },
      {
        eventId: 'dlq_003',
        queueName: 'confidence_projection',
        taskType: 'confidence_delay',
        status: 'delayed',
        occurredAt: new Date(Date.now() - 900_000).toISOString(),
        summary: 'Confidence projection delayed. Deterministic verification remains active.',
        issueKind: 'confidence_delayed',
      },
    ],
  };
}

function artifactForEvent(event: AuditEvent): AuditArtifact {
  if (event.artifactAvailability === 'unavailable') {
    return {
      eventId: event.eventId,
      eventType: event.eventType,
      actorLabel: event.actorLabel,
      agentLabel: event.agentLabel,
      subjectLabel: event.subjectLabel,
      occurredAt: event.occurredAt,
      tier: event.tier,
      signatureStatus: event.signatureStatus,
      availability: 'unavailable',
      unavailableReason: 'Artifact payload not retained for this view-only read event.',
    };
  }
  if (event.artifactAvailability === 'corrupted') {
    return {
      eventId: event.eventId,
      eventType: event.eventType,
      actorLabel: event.actorLabel,
      subjectLabel: event.subjectLabel,
      occurredAt: event.occurredAt,
      tier: event.tier,
      signatureStatus: 'invalid',
      availability: 'corrupted',
      unavailableReason: OPERATIONAL_AUDIT_COPY.artifactInvalidSignature,
    };
  }
  return {
    eventId: event.eventId,
    eventType: event.eventType,
    actorLabel: event.actorLabel,
    agentLabel: event.agentLabel,
    subjectLabel: event.subjectLabel,
    occurredAt: event.occurredAt,
    tier: event.tier,
    signatureStatus: event.signatureStatus,
    availability: 'available',
    semanticTruthHash: 'semantic_hash_placeholder_a1b2',
    sourceSnapshotHash: 'source_snapshot_hash_placeholder_f7g8',
    artifactHash: event.artifactHash ?? OPERATIONAL_AUDIT_COPY.artifactHashPlaceholder,
    signatureHash: 'signature_hash_placeholder_c3d4',
    previousStateHash: event.previousArtifactHash ?? 'prev_state_hash_placeholder_e5f6',
    previousArtifactHash: event.previousArtifactHash,
    idempotencyKey: event.idempotencyKey ?? `idem_${event.eventId}`,
    metadataJson: JSON.stringify(
      {
        event_id: event.eventId,
        event_type: event.eventType,
        envelope_ref: event.envelopeRef ?? null,
      },
      null,
      2,
    ),
    reconstructionStatus:
      event.previousArtifactHash &&
      event.artifactHash &&
      event.previousArtifactHash !== event.artifactHash
        ? 'intact'
        : event.eventId === 'aud_006'
          ? 'broken'
          : 'intact',
    jsonPreview: `{"subject":"${OPERATIONAL_AUDIT_COPY.redactedArtifactPayload}","tier":"${event.tier}"}`,
  };
}

function healthKind(state: SystemHealthState): HealthOutcome['kind'] {
  switch (state) {
    case 'operational':
      return 'health_operational';
    case 'confidence_degraded':
      return 'health_confidence_degraded';
    case 'api_paused':
      return 'health_api_paused';
    case 'integration_attention':
      return 'health_integration_attention';
    case 'loading':
      return 'health_loading';
    case 'fetch_failed':
      return 'health_fetch_failed';
    default:
      return 'health_unknown';
  }
}

function applyAuditFilters(events: AuditEvent[], filters: AuditFilters): AuditEvent[] {
  const logMode = resolveAuditLogMode(filters);
  const tier = auditLogModeToTier(logMode);

  return sortAuditEventsNewestFirst(
    events.filter((event) => {
      if (event.tier !== tier) return false;
      if (filters.systemHealth && event.eventType !== 'system_health') return false;
      if (logMode === 'forensic_log') {
        if (filters.eventType && filters.eventType !== 'all' && event.eventType !== filters.eventType)
          return false;
        if (!eventMatchesForensicCategories(event.eventType, filters.actionCategories)) return false;
        if (filters.claimId) {
          const claimHaystack = [event.claimRef, event.subjectLabel].filter(Boolean).join(' ');
          if (!matchesPartialRef(claimHaystack, filters.claimId)) return false;
        }
      } else {
        if (filters.endpoint && !event.endpoint?.includes(filters.endpoint)) return false;
        if (
          filters.httpStatusCode &&
          filters.httpStatusCode !== 'all' &&
          event.httpStatusCode !== filters.httpStatusCode
        )
          return false;
        if (filters.agent && event.agentLabel !== filters.agent) return false;
      }
      if (filters.actor) {
        const actorQuery = filters.actor.toLowerCase();
        if (!actorSearchHaystack(event).includes(actorQuery)) return false;
      }
      if (filters.envelopeId) {
        const envelopeHaystack = [event.envelopeRef, event.subjectLabel].filter(Boolean).join(' ');
        if (!matchesPartialRef(envelopeHaystack, filters.envelopeId)) return false;
      }
      if (filters.eventId && event.eventId !== filters.eventId) return false;
      if (filters.dateFrom && event.occurredAt < filters.dateFrom) return false;
      if (filters.dateTo && event.occurredAt > filters.dateTo) return false;
      return true;
    }),
  );
}

export function createMockOperationalAuditTransport(
  options: MockOperationalAuditOptions = {},
): OperationalAuditTransport {
  const events = options.auditEvents ?? defaultAuditEvents();
  const diagnostics = options.diagnostics ?? defaultDiagnostics();
  const healthState = options.healthState ?? 'operational';

  const delay = async (signal?: AbortSignal) => {
    if (options.delayMs) {
      await new Promise<void>((resolve, reject) => {
        const timer = setTimeout(resolve, options.delayMs);
        signal?.addEventListener('abort', () => {
          clearTimeout(timer);
          reject(new DOMException('Aborted', 'AbortError'));
        });
      });
    }
  };

  return {
    async listAuditEvents(tenantId, filters, signal) {
      await delay(signal);
      if (!tenantId) return { kind: 'unknown' };
      const role = options.currentUserRole ?? getCurrentUserRole();
      if (options.denyAudit || !canViewAudit(role)) return { kind: 'permission_denied' };
      const filtered = applyAuditFilters(events, filters);
      const tier = auditLogModeToTier(resolveAuditLogMode(filters));
      const tierEvents = events.filter((event) => event.tier === tier);
      if (tierEvents.length === 0) return { kind: 'audit_empty' };
      if (filtered.length === 0) return { kind: 'audit_filtered_empty' };
      const page = sliceCursorPage(filtered, {
        pageSize: filters.pageSize ?? AUDIT_LEDGER_BATCH_SIZE,
        cursor: filters.cursor,
      });
      return {
        kind: 'audit_loaded',
        events: page.rows,
        totalCount: page.totalCount,
        pageSize: page.pageSize,
        hasMore: page.hasMore,
        nextCursor: page.nextCursor,
      };
    },

    async getAuditArtifact(tenantId, eventId, signal) {
      await delay(signal);
      if (!tenantId) return { kind: 'unknown' };
      const role = options.currentUserRole ?? getCurrentUserRole();
      if (options.denyArtifact || !canOpenAuditArtifact(role))
        return { kind: 'artifact_access_denied' };
      const event = events.find((entry) => entry.eventId === eventId);
      if (!event) return { kind: 'not_found' };
      const artifact = artifactForEvent(event);
      if (artifact.availability === 'unavailable') {
        return { kind: 'artifact_unavailable', reason: artifact.unavailableReason ?? 'Unavailable' };
      }
      if (artifact.availability === 'corrupted') {
        return { kind: 'artifact_corrupted', reason: artifact.unavailableReason ?? 'Corrupted' };
      }
      if (artifact.signatureStatus === 'invalid' || artifact.signatureStatus === 'unknown') {
        return { kind: 'artifact_signature_invalid', reason: OPERATIONAL_AUDIT_COPY.artifactInvalidSignature };
      }
      return { kind: 'artifact_loaded', artifact };
    },

    async getDiagnostics(tenantId, query, signal) {
      await delay(signal);
      if (!tenantId) return { kind: 'unknown' };
      const role = options.currentUserRole ?? getCurrentUserRole();
      if (options.denyDiagnostics || !canViewDiagnostics(role)) return { kind: 'permission_denied' };
      if (diagnostics.dlqEvents.length === 0 && diagnostics.summary.taskFailures === 0) {
        return { kind: 'diagnostics_empty' };
      }
      const page = slicePage(diagnostics.dlqEvents, {
        pageSize: query?.pageSize,
        offset: query?.offset,
      });
      const payload: OperationalDiagnosticsPayload = {
        ...diagnostics,
        dlqEvents: page.rows,
      };
      return {
        kind: 'diagnostics_loaded',
        payload,
        dlqEvents: page.rows,
        totalCount: page.totalCount,
        offset: page.offset,
        pageSize: page.pageSize,
        hasMore: page.hasMore,
      };
    },

    async getSystemHealth(tenantId, signal) {
      await delay(signal);
      if (!tenantId) return { kind: 'unknown' };
      const role = options.currentUserRole ?? getCurrentUserRole();
      if (!canViewAudit(role) && !canViewDiagnostics(role)) return { kind: 'permission_denied' };
      return { kind: healthKind(healthState) };
    },
  };
}

export function getDefaultOperationalAuditClient(): OperationalAuditClient {
  if (!defaultClient) {
    defaultClient = createOperationalAuditClient(createMockOperationalAuditTransport());
  }
  return defaultClient;
}

export function setDefaultOperationalAuditClient(client: OperationalAuditClient): void {
  defaultClient = client;
}

export function resetDefaultOperationalAuditClient(): void {
  defaultClient = null;
}
