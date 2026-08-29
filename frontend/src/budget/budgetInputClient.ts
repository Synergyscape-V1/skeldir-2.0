import { getCurrentUserRole } from '../governance/governanceStore';
import { canViewBudgetInput } from '../ledger/permissions';
import {
  BUDGET_CHANNEL_OPTIONS,
  BUDGET_DEFAULT_SPEND_MINOR,
} from './budgetFixtures';
import { LEDGER_COPY } from '../ledger/copy';
import { incrementLedgerRequest, resetLedgerRequestCounter } from '../ledger/requestCounter';
import type { BudgetInputAvailabilityDTO } from '../ledger/types';

export type BudgetInputOutcome =
  | { kind: 'loaded'; input: BudgetInputAvailabilityDTO }
  | { kind: 'permission_denied'; message: string }
  | { kind: 'policy_unavailable'; message: string }
  | { kind: 'blocked_sparse_data'; message: string; input: BudgetInputAvailabilityDTO }
  | { kind: 'trust_api_error'; message: string }
  | { kind: 'unknown_error'; message: string };

export interface BudgetInputClient {
  getBudgetInputAvailability(
    tenantId: string,
    mode?: 'default' | 'sparse' | 'policy_blocked',
    signal?: AbortSignal,
  ): Promise<BudgetInputOutcome>;
}

export function createBudgetInputClient(): BudgetInputClient {
  return {
    async getBudgetInputAvailability(tenantId, mode = 'default') {
      resetLedgerRequestCounter();
      incrementLedgerRequest('budget');

      if (!canViewBudgetInput(getCurrentUserRole())) {
        return { kind: 'permission_denied', message: LEDGER_COPY.permissionDenied };
      }
      if (!tenantId) return { kind: 'unknown_error', message: 'Tenant required' };

      const base: BudgetInputAvailabilityDTO = {
        dateRangeStart: '2026-05-01',
        dateRangeEnd: '2026-06-30',
        eligibleChannels: BUDGET_CHANNEL_OPTIONS.map((c) => c.id),
        spendConstraintMinor: BUDGET_DEFAULT_SPEND_MINOR,
        currencyCode: 'USD',
        objective: 'Maximize verified revenue',
        minimumVerifiedRevenueWindowMinor: 1000000n,
        policyAuthority: mode === 'policy_blocked' ? 'blocked' : 'simulation_only',
        simulationAvailability:
          mode === 'sparse'
            ? 'blocked_insufficient_data'
            : mode === 'policy_blocked'
              ? 'blocked_policy'
              : 'available',
        blockedReason:
          mode === 'sparse'
            ? LEDGER_COPY.budgetBlockedSparse
            : mode === 'policy_blocked'
              ? LEDGER_COPY.budgetBlockedPolicy
              : undefined,
        validationErrors: [],
      };

      if (mode === 'sparse') {
        return { kind: 'blocked_sparse_data', message: LEDGER_COPY.budgetBlockedSparse, input: base };
      }
      if (mode === 'policy_blocked') {
        return { kind: 'policy_unavailable', message: LEDGER_COPY.budgetBlockedPolicy };
      }
      return { kind: 'loaded', input: base };
    },
  };
}

let defaultClient: BudgetInputClient | null = null;
export function getDefaultBudgetInputClient(): BudgetInputClient {
  if (!defaultClient) defaultClient = createBudgetInputClient();
  return defaultClient;
}
export function resetDefaultBudgetInputClient(): void {
  defaultClient = null;
}
