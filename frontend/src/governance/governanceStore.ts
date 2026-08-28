import type { TeamRole } from './types';

let currentUserRole: TeamRole = 'owner';

export function getCurrentUserRole(): TeamRole {
  return currentUserRole;
}

export function setCurrentUserRole(role: TeamRole): void {
  currentUserRole = role;
}

export function resetGovernanceStateForTests(): void {
  currentUserRole = 'owner';
}
