import type { TeamRole } from './types';

export type GovernancePermission =
  | 'view_team'
  | 'manage_team'
  | 'view_agents'
  | 'create_agent_key'
  | 'revoke_agent_key'
  | 'view_policy'
  | 'configure_policy';

const ROLE_PERMISSIONS: Record<TeamRole, readonly GovernancePermission[]> = {
  owner: [
    'view_team',
    'manage_team',
    'view_agents',
    'create_agent_key',
    'revoke_agent_key',
    'view_policy',
    'configure_policy',
  ],
  admin: [
    'view_team',
    'manage_team',
    'view_agents',
    'create_agent_key',
    'revoke_agent_key',
    'view_policy',
    'configure_policy',
  ],
  manager: ['view_team', 'view_agents', 'view_policy'],
  viewer: ['view_team', 'view_agents', 'view_policy'],
  billing_only: ['view_team'],
  unknown_role: [],
};

export function hasPermission(role: TeamRole, permission: GovernancePermission): boolean {
  if (role === 'unknown_role') return false;
  return ROLE_PERMISSIONS[role]?.includes(permission) ?? false;
}

export function canManageTeam(role: TeamRole): boolean {
  return hasPermission(role, 'manage_team');
}

export function canCreateAgentKey(role: TeamRole): boolean {
  return hasPermission(role, 'create_agent_key');
}

export function canConfigurePolicy(role: TeamRole): boolean {
  return hasPermission(role, 'configure_policy');
}

export function canRevokeAgent(role: TeamRole): boolean {
  return hasPermission(role, 'revoke_agent_key');
}
