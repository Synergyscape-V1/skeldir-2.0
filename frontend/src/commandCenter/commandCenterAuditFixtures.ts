import type { AuditActivityRow } from './types';

function minutesAgo(minutes: number): string {
  return new Date(Date.now() - minutes * 60_000).toISOString();
}

/** Canonical Tier B vault-log fixtures — consequence-bearing events only, newest first. */
export const COMMAND_CENTER_AUDIT_ACTIVITY: AuditActivityRow[] = sortNewestFirst([
  {
    eventId: 'evt_artifact_export_01',
    eventType: 'artifact_exported',
    occurredAt: minutesAgo(9),
    tier: 'tier_b',
    actorKind: 'user',
    actorDisplay: 'admin@acme.example',
    actorClientId: 'usr_a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    targetRef: 'env_te_9f2a8b1c',
    envelopeId: 'env_te_9f2a8b1c',
  },
  {
    eventId: 'evt_policy_decision_01',
    eventType: 'policy_decision_rendered',
    occurredAt: minutesAgo(23),
    tier: 'tier_b',
    actorKind: 'user',
    actorDisplay: 'finance@acme.example',
    actorClientId: 'usr_b2c3d4e5-f6a7-8901-bcde-f12345678901',
    targetRef: 'env_te_4c7d1e9a',
    envelopeId: 'env_te_4c7d1e9a',
  },
  {
    eventId: 'evt_exception_update_01',
    eventType: 'exception_case_updated',
    occurredAt: minutesAgo(28),
    tier: 'tier_b',
    actorKind: 'user',
    actorDisplay: 'ops@acme.example',
    actorClientId: 'usr_c3d4e5f6-a7b8-9012-cdef-123456789012',
    targetRef: 'exc_queue_88fa',
    envelopeId: 'env_te_4c7d1e9a',
  },
  {
    eventId: 'evt_bayesian_fit_01',
    eventType: 'bayesian_fit_completed',
    occurredAt: minutesAgo(46),
    tier: 'tier_b',
    actorKind: 'agent',
    actorDisplay: 'Skeldir-MCP',
    actorClientId: 'agt_mcp_client_7e21d0f4',
    targetRef: 'env_te_2b9f6e31',
    envelopeId: 'env_te_2b9f6e31',
  },
]);

function sortNewestFirst(rows: AuditActivityRow[]): AuditActivityRow[] {
  return [...rows].sort((a, b) => b.occurredAt.localeCompare(a.occurredAt));
}
