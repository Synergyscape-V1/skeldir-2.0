import { buildClaimTrustDrawerHref } from '../trustIndex/envelopeClaimRouting';
import { OPERATIONAL_AUDIT_COPY } from './copy';
import type { AuditEvent } from './types';
import { formatForensicExecutiveActivityLabel } from './forensicExecutiveDisplay';

export interface ForensicBusinessDetailContent {
  headline: string;
  summary: string;
  primaryActionLabel?: string;
  primaryActionHref?: string;
}

export function resolveForensicBusinessDetail(event: AuditEvent): ForensicBusinessDetailContent {
  const activity = formatForensicExecutiveActivityLabel(event.eventType);
  const copy = OPERATIONAL_AUDIT_COPY.forensicBusinessDetail;

  switch (event.eventType) {
    case 'artifact_exported':
      return {
        headline: activity,
        summary: copy.exportedSummary,
        primaryActionLabel: copy.signatureVerificationAction,
        primaryActionHref: event.envelopeRef
          ? buildClaimTrustDrawerHref(event.envelopeRef)
          : undefined,
      };
    case 'policy_decision_rendered':
      return {
        headline: activity,
        summary: copy.policyDecisionSummary,
        primaryActionLabel: copy.reviewPolicyAction,
        primaryActionHref: '/app/settings/policy',
      };
    case 'proposal_exported':
      return {
        headline: activity,
        summary: copy.proposalSummary,
        primaryActionLabel: copy.submitProposalAction,
        primaryActionHref: `/app/budget/${event.proposalRef ?? 'sim_0001'}`,
      };
    case 'exception_case_updated':
      return {
        headline: activity,
        summary: copy.exceptionSummary,
        primaryActionLabel: copy.resolveExceptionAction,
        primaryActionHref: `/app/exceptions?case=${encodeURIComponent(event.subjectLabel)}`,
      };
    default:
      return {
        headline: activity,
        summary: copy.defaultSummary,
      };
  }
}
