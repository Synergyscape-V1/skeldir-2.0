import type { TeamRole } from '../governance/types';

export type OperationalAuditPermission =
  | 'view_diagnostics'
  | 'view_audit'
  | 'open_audit_artifact';

const ROLE_PERMISSIONS: Record<TeamRole, readonly OperationalAuditPermission[]> = {
  owner: ['view_diagnostics', 'view_audit', 'open_audit_artifact'],
  admin: ['view_diagnostics', 'view_audit', 'open_audit_artifact'],
  manager: ['view_diagnostics', 'view_audit', 'open_audit_artifact'],
  viewer: ['view_audit'],
  billing_only: [],
  unknown_role: [],
};

export function hasOperationalPermission(
  role: TeamRole,
  permission: OperationalAuditPermission,
): boolean {
  if (role === 'unknown_role') return false;
  return ROLE_PERMISSIONS[role]?.includes(permission) ?? false;
}

export function canViewDiagnostics(role: TeamRole): boolean {
  return hasOperationalPermission(role, 'view_diagnostics');
}

export function canViewAudit(role: TeamRole): boolean {
  return hasOperationalPermission(role, 'view_audit');
}

export function canOpenAuditArtifact(role: TeamRole): boolean {
  return hasOperationalPermission(role, 'open_audit_artifact');
}
