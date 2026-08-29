import { FORENSIC_AUDIT_EVENT_TYPES, type ForensicAuditEventType } from '../commandCenter/auditActivityPolicy';
import { ERROR_COPY } from '../lib/copy';
import type { PolicyAuthorityState } from '../lib/types';
import { truncateIdentifier } from '../lib/truncateIdentifier';
import type { AuditEvent, AuditEventType, ForensicChainVerification } from './types';

const FORENSIC_EXECUTIVE_ACTION_LABELS: Record<ForensicAuditEventType, string> = {
  artifact_exported: 'Exported Signed Report',
  proposal_exported: 'Budget Proposal Generated',
  proposal_reviewed: 'Budget Proposal Reviewed',
  policy_decision_rendered: 'Policy Decision Made',
  exception_case_updated: 'Exception Case Updated',
  bayesian_fit_completed: 'Confidence Model Recalculated',
  dispatch_executed: 'Outbound Action Sent',
  dispatch_suppressed: 'Outbound Action Blocked',
};

const FORENSIC_ACTION_SET = new Set<string>(FORENSIC_AUDIT_EVENT_TYPES);

export function formatForensicTimestampUtc(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return ERROR_COPY.missingRequiredProp('occurredAt');
  }
  const year = date.getUTCFullYear();
  const month = String(date.getUTCMonth() + 1).padStart(2, '0');
  const day = String(date.getUTCDate()).padStart(2, '0');
  const hour = String(date.getUTCHours()).padStart(2, '0');
  const minute = String(date.getUTCMinutes()).padStart(2, '0');
  const second = String(date.getUTCSeconds()).padStart(2, '0');
  return `${year}-${month}-${day} ${hour}:${minute}:${second} UTC`;
}

export function formatForensicExecutiveActivityLabel(eventType: AuditEventType | string): string {
  if (FORENSIC_ACTION_SET.has(eventType)) {
    return FORENSIC_EXECUTIVE_ACTION_LABELS[eventType as ForensicAuditEventType];
  }
  if (eventType === 'unknown') {
    return 'Unknown action';
  }
  return eventType.replace(/_/g, ' ');
}

export function formatForensicExecutiveActor(row: AuditEvent): string {
  if (row.actorKind === 'agent' || row.agentLabel) {
    return `Agent: ${row.agentLabel ?? row.actorLabel}`;
  }
  if (row.actorLabel.includes('@')) {
    return `Admin: ${row.actorLabel}`;
  }
  return row.actorLabel;
}

export function forensicActorTechnicalId(row: AuditEvent): string | undefined {
  return row.actorClientId;
}

export function formatForensicExecutiveSubject(row: AuditEvent): string {
  if (row.businessSubjectLabel) {
    return row.businessSubjectLabel;
  }
  return truncateIdentifier(row.subjectLabel);
}

export function resolveForensicChainVerification(row: AuditEvent): ForensicChainVerification {
  if (row.chainVerification) {
    return row.chainVerification;
  }
  if (row.signatureStatus === 'invalid' || row.artifactAvailability === 'corrupted') {
    return 'review_required';
  }
  return 'intact';
}

export function resolveForensicPolicyAuthority(row: AuditEvent): PolicyAuthorityState | null {
  if (row.policyAuthority) {
    return row.policyAuthority;
  }
  switch (row.eventType) {
    case 'proposal_exported':
      return 'proposal_required';
    case 'policy_decision_rendered':
      return 'approval_required';
    case 'artifact_exported':
      return 'blocked';
    case 'exception_case_updated':
      return 'blocked';
    case 'dispatch_suppressed':
      return 'blocked';
    default:
      return null;
  }
}

export type ForensicExecutiveStatus =
  | { kind: 'policy'; state: PolicyAuthorityState }
  | { kind: 'exported' }
  | { kind: 'proposal_generated' };

export function resolveForensicExecutiveStatus(row: AuditEvent): ForensicExecutiveStatus {
  if (row.eventType === 'artifact_exported') {
    return { kind: 'exported' };
  }
  if (row.eventType === 'proposal_exported') {
    return { kind: 'proposal_generated' };
  }
  const policy = resolveForensicPolicyAuthority(row);
  if (policy) {
    return { kind: 'policy', state: policy };
  }
  return { kind: 'policy', state: 'blocked' };
}

export function resolveForensicEventDetailPath(eventId: string): string {
  return `/app/audit/events/${eventId}`;
}
