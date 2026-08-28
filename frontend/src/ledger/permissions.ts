import type { TeamRole } from '../governance/types';

export type LedgerPermission =
  | 'view_claims'
  | 'view_trust_index'
  | 'view_channels'
  | 'view_benchmarks'
  | 'view_exceptions'
  | 'view_budget_input';

const ROLE_LEDGER_PERMISSIONS: Record<TeamRole, readonly LedgerPermission[]> = {
  owner: [
    'view_claims',
    'view_trust_index',
    'view_channels',
    'view_benchmarks',
    'view_exceptions',
    'view_budget_input',
  ],
  admin: [
    'view_claims',
    'view_trust_index',
    'view_channels',
    'view_benchmarks',
    'view_exceptions',
    'view_budget_input',
  ],
  manager: [
    'view_claims',
    'view_trust_index',
    'view_channels',
    'view_benchmarks',
    'view_exceptions',
    'view_budget_input',
  ],
  viewer: ['view_claims', 'view_trust_index', 'view_channels', 'view_benchmarks', 'view_exceptions'],
  billing_only: [],
  unknown_role: [],
};

export function hasLedgerPermission(role: TeamRole, permission: LedgerPermission): boolean {
  if (role === 'unknown_role') return false;
  return ROLE_LEDGER_PERMISSIONS[role]?.includes(permission) ?? false;
}

export function canViewClaims(role: TeamRole): boolean {
  return hasLedgerPermission(role, 'view_claims');
}

export function canViewTrustIndex(role: TeamRole): boolean {
  return hasLedgerPermission(role, 'view_trust_index');
}

export function canViewChannels(role: TeamRole): boolean {
  return hasLedgerPermission(role, 'view_channels');
}

export function canViewBenchmarks(role: TeamRole): boolean {
  return hasLedgerPermission(role, 'view_benchmarks');
}

export function canViewExceptions(role: TeamRole): boolean {
  return hasLedgerPermission(role, 'view_exceptions');
}

export function canViewBudgetInput(role: TeamRole): boolean {
  return hasLedgerPermission(role, 'view_budget_input');
}
