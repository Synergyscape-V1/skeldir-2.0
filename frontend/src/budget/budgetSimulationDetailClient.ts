import { getCurrentUserRole } from '../governance/governanceStore';
import { canViewBudgetInput } from '../ledger/permissions';
import { DETAIL_COPY } from '../detail/copy';
import { incrementDetailRequest, resetDetailRequestCounter } from '../detail/requestCounter';
import { validateBudgetSimulationDetailDto } from '../detail/detailDtoValidation';
import type { BudgetSimulationDetailDTO, BudgetSimulationDetailOutcome } from '../detail/types';
import type { PolicyAuthorityState } from '../lib/types';

let policyAuthorityOverride: PolicyAuthorityState | null = null;

export function setBudgetDetailPolicyAuthorityForTests(policy: PolicyAuthorityState | null): void {
  policyAuthorityOverride = policy;
}

export function resetBudgetSimulationDetailTestHooks(): void {
  policyAuthorityOverride = null;
}

export function createBudgetSimulationDetailClient(): {
  getBudgetSimulationDetail(
    tenantId: string,
    simulationId: string,
    signal?: AbortSignal,
  ): Promise<BudgetSimulationDetailOutcome>;
} {
  return {
    async getBudgetSimulationDetail(tenantId, simulationId, signal) {
      if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');
      resetDetailRequestCounter();
      incrementDetailRequest('budget-detail');

      if (!canViewBudgetInput(getCurrentUserRole())) {
        return { kind: 'permission_denied', message: DETAIL_COPY.permissionDenied };
      }
      if (!tenantId || !/^sim_\d{4}$/.test(simulationId)) {
        return { kind: 'not_found', message: DETAIL_COPY.notFound };
      }

      const detail: BudgetSimulationDetailDTO = {
        simulationId,
        tenantId,
        simulationStatus: 'ready',
        inputAssumptions: [
          '30-day verified revenue window',
          'Spend constraint from policy-approved envelope',
        ],
        verifiedRevenueBasisMinor: 2500000n,
        currencyCode: 'USD',
        confidence: {
          status: 'unavailable',
          reason: 'Sparse channel history — simulation uses deterministic verified revenue only.',
        },
        benchmark: {
          status: 'available',
          decisionSafeBenchmark: '9.8%',
          evidenceClass: 'tenant_longitudinal',
          coverageClass: 'rolled_up',
        },
        policyAuthority:
          policyAuthorityOverride ??
          (simulationId === 'sim_0002' ? 'approval_required' : 'proposal_required'),
        projectedAllocation: [
          { channel: 'meta_ads', shareBps: 4200 },
          { channel: 'google_ads', shareBps: 3800 },
          { channel: 'tiktok_ads', shareBps: 2000 },
        ],
        riskCaveats: [
          'LP matrix may be underdetermined for low-conversion channels.',
          'No auto-optimize or guaranteed lift semantics apply.',
        ],
        auditReference: `aud_${simulationId}`,
        versionStamp: `v_${simulationId}_1`,
      };

      const validation = validateBudgetSimulationDetailDto(detail, simulationId, tenantId);
      if (!validation.ok) {
        return {
          kind: validation.kind,
          message:
            validation.kind === 'object_id_mismatch'
              ? DETAIL_COPY.objectIdMismatch
              : DETAIL_COPY.scopeDenied,
        };
      }

      return { kind: 'loaded', detail };
    },
  };
}

let defaultClient: ReturnType<typeof createBudgetSimulationDetailClient> | null = null;

export function getDefaultBudgetSimulationDetailClient() {
  if (!defaultClient) defaultClient = createBudgetSimulationDetailClient();
  return defaultClient;
}

export function resetDefaultBudgetSimulationDetailClient(): void {
  defaultClient = null;
  resetBudgetSimulationDetailTestHooks();
}
