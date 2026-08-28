import { FORENSIC_AUDIT_EVENT_TYPES, type ForensicAuditEventType } from '../commandCenter/auditActivityPolicy';
import type { AuditEventType, AuditTier } from './types';

const FORENSIC_ACTION_LABELS: Record<ForensicAuditEventType, string> = {
  artifact_exported: 'Signed report exported',
  proposal_exported: 'Budget proposal exported',
  proposal_reviewed: 'Budget proposal reviewed',
  policy_decision_rendered: 'Policy rule applied',
  exception_case_updated: 'Exception case updated',
  bayesian_fit_completed: 'Confidence model recalculated',
  dispatch_executed: 'Outbound action sent',
  dispatch_suppressed: 'Outbound action blocked',
};

const FORENSIC_ACTION_SET = new Set<string>(FORENSIC_AUDIT_EVENT_TYPES);

export const FORENSIC_BADGE_LABEL = 'Forensic';

export const FORENSIC_BADGE_TOOLTIP =
  'This action created a cryptographically signed, tamper-proof audit record.';

export const VIEW_RECORD_CLASS_LABEL = 'View';

export const VIEW_RECORD_CLASS_TOOLTIP =
  'A routine read or view event. This is not a signed forensic record.';

export function formatForensicActionLabel(eventType: AuditEventType | string): string {
  if (FORENSIC_ACTION_SET.has(eventType)) {
    return FORENSIC_ACTION_LABELS[eventType as ForensicAuditEventType];
  }
  if (eventType === 'unknown') {
    return 'Unknown action';
  }
  return eventType.replace(/_/g, ' ');
}

export function formatAuditRecordClassLabel(tier: AuditTier): string {
  switch (tier) {
    case 'tier_b':
      return FORENSIC_BADGE_LABEL;
    case 'tier_a':
      return VIEW_RECORD_CLASS_LABEL;
    default:
      return 'Unknown';
  }
}

export function auditRecordClassTooltip(tier: AuditTier): string {
  switch (tier) {
    case 'tier_b':
      return FORENSIC_BADGE_TOOLTIP;
    case 'tier_a':
      return VIEW_RECORD_CLASS_TOOLTIP;
    default:
      return 'Record class could not be determined.';
  }
}

const READ_EVENT_TYPE_LABELS: Partial<Record<AuditEventType, string>> = {
  trust_access: 'Trust access viewed',
  trust_api_read: 'Trust API read',
  simulation_read: 'Simulation viewed',
  system_health: 'System health event',
  integration_event: 'Integration event',
  task_failure: 'Task failure',
  policy_read: 'Policy viewed',
  artifact_read: 'Artifact viewed',
};

export function formatAuditRecordClassFilterLabel(tier: AuditTier | 'all'): string {
  if (tier === 'all') {
    return 'All record classes';
  }
  return formatAuditRecordClassLabel(tier);
}

export function formatAuditEventTypeFilterLabel(eventType: AuditEventType | 'all'): string {
  if (eventType === 'all') {
    return 'All actions';
  }
  if (FORENSIC_ACTION_SET.has(eventType)) {
    return FORENSIC_ACTION_LABELS[eventType as ForensicAuditEventType];
  }
  return READ_EVENT_TYPE_LABELS[eventType] ?? eventType.replace(/_/g, ' ');
}

export function truncateIdempotencyKey(key: string, max = 20): string {
  if (key.length <= max) return key;
  const head = Math.max(4, Math.floor((max - 1) / 2));
  const tail = max - head - 1;
  return `${key.slice(0, head)}…${key.slice(-tail)}`;
}
