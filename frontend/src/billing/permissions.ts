import type { TeamRole } from '../governance/types';

export function canViewBilling(role: TeamRole): boolean {
  return role === 'owner' || role === 'admin' || role === 'billing_only' || role === 'manager' || role === 'viewer';
}

export function canManageBilling(role: TeamRole): boolean {
  return role === 'owner' || role === 'admin' || role === 'billing_only';
}
