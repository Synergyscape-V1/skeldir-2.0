import type { TeamRole } from '../governance/types';

export type ActionPermission =
  | 'export_claim_report'
  | 'export_trust_artifact'
  | 'export_audit_reconstruction'
  | 'submit_budget_proposal'
  | 'perform_exception_action';

const ROLE_ACTION_PERMISSIONS: Record<TeamRole, readonly ActionPermission[]> = {
  owner: [
    'export_claim_report',
    'export_trust_artifact',
    'export_audit_reconstruction',
    'submit_budget_proposal',
    'perform_exception_action',
  ],
  admin: [
    'export_claim_report',
    'export_trust_artifact',
    'export_audit_reconstruction',
    'submit_budget_proposal',
    'perform_exception_action',
  ],
  manager: [
    'export_claim_report',
    'export_trust_artifact',
    'export_audit_reconstruction',
    'submit_budget_proposal',
    'perform_exception_action',
  ],
  viewer: [],
  billing_only: [],
  unknown_role: [],
};

export function hasActionPermission(role: TeamRole, permission: ActionPermission): boolean {
  if (role === 'unknown_role') return false;
  return ROLE_ACTION_PERMISSIONS[role]?.includes(permission) ?? false;
}

export function permissionDeniedCopy(permission: ActionPermission): string {
  return `Missing permission: ${permission.replace(/_/g, ' ')}.`;
}
