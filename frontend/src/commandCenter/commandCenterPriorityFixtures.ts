import { COMMAND_CENTER_COPY } from './copy';
import type { PriorityIssue } from './types';

/**
 * Canonical supervisory projection fixtures — pre-filtered, pre-sorted highlight reel.
 * Production UI consumes the backend projection as-is; these fixtures simulate that contract.
 */
export const COMMAND_CENTER_PRIORITY_ISSUES: PriorityIssue[] = [
  {
    id: 'pri_policy_meta_budget',
    severity: 'policy_approval_required',
    title: COMMAND_CENTER_COPY.priorityIssues.metaBudgetTitle,
    explanation: COMMAND_CENTER_COPY.priorityIssues.metaBudgetExplanation,
    subjectRef: 'sim_0002',
    policyAuthority: 'approval_required',
    actionLabel: COMMAND_CENTER_COPY.priorityIssues.metaBudgetAction,
    actionHref: '/app/budget/sim_0002?focus=policy',
    sourceLink: '/app/budget/sim_0002',
    auditRef: 'aud_policy_meta_budget',
  },
  {
    id: 'pri_google_discrepancy',
    severity: 'verified_discrepancy_over_threshold',
    title: COMMAND_CENTER_COPY.priorityIssues.googleDiscrepancyTitle,
    explanation: COMMAND_CENTER_COPY.priorityIssues.googleDiscrepancyExplanation,
    // claim_0010 = baseClaimRow(9): google_ads + flagged discrepancy (index%4===1 && index%3===0).
    // claim_0008 was linkedin_ads — mismatched the Google Ads issue copy.
    subjectRef: 'claim_0010',
    policyAuthority: 'blocked',
    actionLabel: COMMAND_CENTER_COPY.priorityIssues.googleDiscrepancyAction,
    actionHref: '/app/claims/claim_0010',
    sourceLink: '/app/claims/claim_0010',
    auditRef: 'aud_claim_discrepancy_google',
  },
  {
    id: 'pri_tiktok_confidence',
    severity: 'confidence_unavailable_where_action_requested',
    title: COMMAND_CENTER_COPY.priorityIssues.tiktokConfidenceTitle,
    explanation: COMMAND_CENTER_COPY.priorityIssues.tiktokConfidenceExplanation,
    subjectRef: 'env_0003',
    policyAuthority: 'simulation_only',
    actionLabel: COMMAND_CENTER_COPY.priorityIssues.tiktokConfidenceAction,
    actionHref: '/app/claims/claim_0003?trustEnvelope=env_0003&trustFocus=confidence',
    sourceLink: '/app/claims/claim_0003?trustEnvelope=env_0003',
  },
];
