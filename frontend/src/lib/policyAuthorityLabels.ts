import type { PolicyAuthorityState } from './types';

/**
 * UI labels for policy authority states.
 * Enum keys stay backend-contractual; only presentation strings live here.
 */
export const POLICY_AUTHORITY_UI_LABELS: Record<PolicyAuthorityState, string> = {
  blocked: 'Blocked',
  simulation_only: 'Simulation only',
  proposal_required: 'Proposal required',
  approval_required: 'Pending Certification',
  auto_executable_within_policy: 'Auto-executable within policy',
};

/** Dense table / chip labels — same register, shorter where density requires. */
export const POLICY_AUTHORITY_TABLE_LABELS: Record<PolicyAuthorityState, string> = {
  blocked: 'Blocked',
  simulation_only: 'Simulation',
  proposal_required: 'Proposal',
  approval_required: 'Pending Certification',
  auto_executable_within_policy: 'Auto-exec',
};

export const POLICY_AUTHORITY_EXPLANATION = {
  approvalRequired:
    'Awaiting certification by Finance Approver. Simulation is ready—notification sent.',
  blockedSparse:
    'Simulation unavailable: Insufficient verified conversions. Expand your date range or include more channels.',
} as const;
