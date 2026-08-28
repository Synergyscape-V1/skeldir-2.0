import { getCurrentUserRole } from '../governance/governanceStore';
import { canViewBudgetInput } from '../ledger/permissions';
import { ERROR_COPY, UNAVAILABLE_COPY } from '../lib/copy';
import { incrementLedgerRequest, resetLedgerRequestCounter } from '../ledger/requestCounter';
import {
  BUDGET_CHANNEL_OPTIONS,
  BUDGET_DEFAULT_CURRENCY,
  BUDGET_DEFAULT_SPEND_MINOR,
  channelColorForId,
  channelLabelForId,
} from './budgetFixtures';
import { isFormEligibleForGeneration, computeSufficiencySummary } from './budgetSufficiency';
import type {
  BudgetSimulationFormState,
  BudgetSimulationResultDTO,
  GenerateSimulationOutcome,
} from './budgetSimulationTypes';

export type BudgetSimulationClientMode = 'default' | 'sparse' | 'trust_api_error' | 'policy_blocked';

export interface BudgetSimulationClient {
  generateSimulation(
    tenantId: string,
    form: BudgetSimulationFormState,
    mode?: BudgetSimulationClientMode,
    signal?: AbortSignal,
  ): Promise<GenerateSimulationOutcome>;
}

function buildAllocation(
  channelIds: string[],
  totalMinor: bigint,
  sharesBps: number[],
): BudgetSimulationResultDTO['currentAllocation'] {
  return channelIds.map((channelId, index) => ({
    channelId,
    channelLabel: channelLabelForId(channelId),
    amountMinor: (totalMinor * BigInt(sharesBps[index] ?? 0)) / 10000n,
    shareBps: sharesBps[index] ?? 0,
    color: channelColorForId(channelId),
  }));
}

function buildSourceEnvelopes(channelIds: string[]): BudgetSimulationResultDTO['sourceTrustEnvelopes'] {
  const revenues = [4_820_000n, 3_150_000n, 1_940_000n, 980_000n, 610_000n];
  return channelIds.map((channelId, index) => ({
    envelopeId: `env_budget_${index + 1}`,
    channelId,
    channelLabel: channelLabelForId(channelId),
    authority: index === 0 ? 'deterministic' : index === 1 ? 'deterministic' : 'probabilistic',
    contributionRole: index < 2 ? 'primary' : 'supporting',
    verifiedRevenueMinor: revenues[index] ?? 500_000n,
  }));
}

export function createBudgetSimulationClient(): BudgetSimulationClient {
  return {
    async generateSimulation(tenantId, form, mode = 'default', signal) {
      resetLedgerRequestCounter();
      incrementLedgerRequest('budget_generate');

      if (signal?.aborted) {
        return { kind: 'error', message: 'Request aborted' };
      }

      if (!canViewBudgetInput(getCurrentUserRole())) {
        return { kind: 'permission_denied', message: ERROR_COPY.permissionDenied };
      }

      if (!tenantId) {
        return { kind: 'error', message: 'Tenant required' };
      }

      if (mode === 'trust_api_error') {
        return { kind: 'trust_api_error', message: ERROR_COPY.trustApiReadFailed };
      }

      const summary = computeSufficiencySummary(form, {
        policyBlocked: mode === 'policy_blocked',
        trustApiOperational: true,
      });

      if (mode === 'sparse' || !isFormEligibleForGeneration(summary)) {
        return {
          kind: 'blocked_sparse_data',
          message: UNAVAILABLE_COPY.blockedSimulationBody,
        };
      }

      const channelIds =
        form.channelIds.length > 0
          ? form.channelIds
          : BUDGET_CHANNEL_OPTIONS.map((c) => c.id);

      const total = form.spendConstraintMinor > 0n ? form.spendConstraintMinor : BUDGET_DEFAULT_SPEND_MINOR;
      const currentShares = [2800, 2400, 1600, 1800, 1400];
      const simulatedShares = [3200, 2200, 1400, 1600, 1600];

      const currentTotalRevenue = 10_500_000n;
      const projectedTotalRevenue = 11_487_000n;
      const currentBlendedRoasBps = 310;
      const projectedBlendedRoasBps = 340;
      const currentBlendedCacBps = 323;
      const projectedBlendedCacBps = 294;

      const result: BudgetSimulationResultDTO = {
        simulationId: 'sim_0001',
        versionStamp: 'v_sim_0001_1',
        currencyCode: form.currencyCode || BUDGET_DEFAULT_CURRENCY,
        currentAllocation: buildAllocation(channelIds, total, currentShares),
        simulatedAllocation: buildAllocation(channelIds, total, simulatedShares),
        // Baseline values
        currentBlendedRoasBps,
        currentTotalRevenueMinor: currentTotalRevenue,
        currentBlendedCacBps,
        // Projected values
        projectedBlendedRoasBps,
        projectedTotalRevenueMinor: projectedTotalRevenue,
        projectedBlendedCacBps,
        // Delta values
        expectedRevenueLiftBps: 940,
        blendedCacChangeBps: -710,
        spendDeltaBps: 0,
        // Confidence and sensitivity (probabilistic example)
        confidenceInterval: {
          lowerBps: 720,
          upperBps: 1160,
          authority: 'probabilistic',
        },
        sensitivityRange: {
          optimisticBps: 1250,
          pessimisticBps: 630,
          authority: 'probabilistic',
        },
        impactAuthority: 'probabilistic',
        sourceTrustEnvelopes: buildSourceEnvelopes(channelIds),
        policyAuthority: mode === 'policy_blocked' ? 'blocked' : 'approval_required',
        auditReference: 'aud_sim_0001',
        auditArtifactStatus: 'written',
      };

      return { kind: 'success', result };
    },
  };
}

let defaultClient: BudgetSimulationClient | null = null;

export function getDefaultBudgetSimulationClient(): BudgetSimulationClient {
  if (!defaultClient) defaultClient = createBudgetSimulationClient();
  return defaultClient;
}

export function resetDefaultBudgetSimulationClient(): void {
  defaultClient = null;
}
