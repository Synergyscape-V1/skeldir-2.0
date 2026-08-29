/** Consequence-bearing Tier B event types shown on the Command Center audit strip. */
export const FORENSIC_AUDIT_EVENT_TYPES = [
  'artifact_exported',
  'proposal_exported',
  'proposal_reviewed',
  'policy_decision_rendered',
  'exception_case_updated',
  'bayesian_fit_completed',
  'dispatch_executed',
  'dispatch_suppressed',
] as const;

export type ForensicAuditEventType = (typeof FORENSIC_AUDIT_EVENT_TYPES)[number];

/** Tier A read noise — must never appear on the vault log strip. */
export const FORBIDDEN_AUDIT_STRIP_EVENT_TYPES = [
  'trust_api_read',
  'simulation_read',
  'trust_access',
  'artifact_read',
  'policy_read',
] as const;

export const AUDIT_ACTIVITY_STRIP_SIZE = 4;
export const AUDIT_ACTIVITY_POLL_INTERVAL_MS = 60_000;

const FORENSIC_SET = new Set<string>(FORENSIC_AUDIT_EVENT_TYPES);
const FORBIDDEN_SET = new Set<string>(FORBIDDEN_AUDIT_STRIP_EVENT_TYPES);

export function isForensicAuditEventType(value: string): value is ForensicAuditEventType {
  return FORENSIC_SET.has(value);
}

export function isAllowedAuditStripEvent(eventType: string, tier: string): boolean {
  if (tier !== 'tier_b') return false;
  if (FORBIDDEN_SET.has(eventType)) return false;
  return isForensicAuditEventType(eventType);
}

export function sortAuditActivityNewestFirst<T extends { occurredAt: string }>(rows: T[]): T[] {
  return [...rows].sort((a, b) => b.occurredAt.localeCompare(a.occurredAt));
}
