import type { PolicyAuthorityState, TenantPolicyMode } from '../lib/types';
import { ERROR_COPY } from '../lib/copy';
import { POLICY_AUTHORITY_EXPLANATION } from '../lib/policyAuthorityLabels';

export type ActionConsequenceClass = 'external_artifact' | 'workflow_mutation' | 'read_copy';

export function isPolicyBlockedForAction(
  policy: PolicyAuthorityState,
  consequence: ActionConsequenceClass,
): boolean {
  if (policy === 'blocked') return true;
  if (policy === 'simulation_only' && consequence !== 'read_copy') return true;
  return false;
}

export function requiresConfirmation(
  policy: PolicyAuthorityState,
  consequence: ActionConsequenceClass,
): boolean {
  if (isPolicyBlockedForAction(policy, consequence)) return false;
  return (
    consequence === 'external_artifact' ||
    consequence === 'workflow_mutation' ||
    policy === 'approval_required' ||
    policy === 'proposal_required'
  );
}

export function isAutoExecutableConflict(
  policy: PolicyAuthorityState,
  tenantPolicyMode: TenantPolicyMode = 'design_partner',
): boolean {
  return policy === 'auto_executable_within_policy' && tenantPolicyMode === 'design_partner';
}

export function policyBlockedCopy(policy: PolicyAuthorityState): string {
  if (policy === 'blocked') return 'Action authority is blocked for this object.';
  if (policy === 'simulation_only') return 'Simulation-only policy forbids external or consequence-bearing actions.';
  if (policy === 'proposal_required') return 'This action requires a governed proposal flow.';
  if (policy === 'approval_required') return POLICY_AUTHORITY_EXPLANATION.approvalRequired;
  return 'Policy authority prevents this action.';
}

export function validatePolicyBeforeSubmit(
  policy: PolicyAuthorityState,
  tenantPolicyMode: TenantPolicyMode,
  consequence: ActionConsequenceClass,
): { ok: true } | { ok: false; copy: string } {
  if (isAutoExecutableConflict(policy, tenantPolicyMode)) {
    return { ok: false, copy: ERROR_COPY.invalidPolicyState };
  }
  if (isPolicyBlockedForAction(policy, consequence)) {
    return { ok: false, copy: policyBlockedCopy(policy) };
  }
  return { ok: true };
}
