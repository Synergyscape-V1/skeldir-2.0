import type { TeamRole } from '../governance/types';

const SUPERVISORY_ACTION_ROLES: readonly TeamRole[] = ['owner', 'admin', 'manager'];

export function canUseCommandCenterSupervisoryActions(role: TeamRole): boolean {
  return SUPERVISORY_ACTION_ROLES.includes(role);
}
