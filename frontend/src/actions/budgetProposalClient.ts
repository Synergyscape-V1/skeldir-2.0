import { getCurrentUserRole } from '../governance/governanceStore';
import { getDefaultBudgetSimulationDetailClient } from '../budget/budgetSimulationDetailClient';
import { ACTION_COPY } from './copy';
import {
  createActionId,
  createAuditEventId,
  generateIdempotencyKey,
  getIdempotencyReplay,
  markIdempotencyPending,
  recordIdempotencySuccess,
} from './idempotency';
import { hasActionPermission } from './permissions';
import { validatePolicyBeforeSubmit } from './policyGate';
import { checkSubsystemSafetyForExternalAction } from './systemSafety';
import type { BudgetProposalPreview, GovernedActionOutcome } from './types';

export type BudgetProposalTestMode =
  | 'default'
  | 'permission_denied'
  | 'replay'
  | 'stale'
  | 'blocked_policy'
  | 'subsystem_unsafe';

let testMode: BudgetProposalTestMode = 'default';

export function setBudgetProposalTestMode(mode: BudgetProposalTestMode): void {
  testMode = mode;
}

export function resetBudgetProposalTestMode(): void {
  testMode = 'default';
}

export function createBudgetProposalClient() {
  return {
    async buildProposalPreview(
      tenantId: string,
      simulationId: string,
    ): Promise<BudgetProposalPreview | null> {
      const outcome = await getDefaultBudgetSimulationDetailClient().getBudgetSimulationDetail(tenantId, simulationId);
      if (outcome.kind !== 'loaded') return null;
      const d = outcome.detail;
      return {
        simulationId: d.simulationId,
        assumptions: d.inputAssumptions,
        verifiedRevenueBasisMinor: d.verifiedRevenueBasisMinor.toString(),
        currencyCode: d.currencyCode,
        confidenceCaveat:
          d.confidence.status === 'unavailable'
            ? `Sparse data: ${d.confidence.reason ?? 'insufficient observations'}`
            : 'Confidence interval available for review only',
        benchmarkContext:
          d.benchmark.status === 'unavailable'
            ? 'Benchmark unavailable'
            : `${d.benchmark.decisionSafeBenchmark} (${d.benchmark.evidenceClass})`,
        policyAuthority: d.policyAuthority,
        riskCaveats: d.riskCaveats,
        projectedAllocation: d.projectedAllocation,
      };
    },

    async submitBudgetProposal(
      tenantId: string,
      simulationId: string,
      versionStamp: string,
      idempotencyKey?: string,
    ): Promise<GovernedActionOutcome> {
      const key =
        idempotencyKey ?? generateIdempotencyKey(tenantId, 'budget_simulation', simulationId, 'submit_proposal');

      if (testMode === 'permission_denied' || !hasActionPermission(getCurrentUserRole(), 'submit_budget_proposal')) {
        return { status: 'permission_denied', idempotencyKey: key, objectId: simulationId, objectType: 'budget_simulation', tenantId, safeUserCopy: ACTION_COPY.permissionDenied };
      }

      const detailOutcome = await getDefaultBudgetSimulationDetailClient().getBudgetSimulationDetail(tenantId, simulationId);
      if (detailOutcome.kind !== 'loaded') {
        return { status: 'artifact_unavailable', idempotencyKey: key, objectId: simulationId, objectType: 'budget_simulation', tenantId, safeUserCopy: ACTION_COPY.artifactUnavailable };
      }

      const detail = detailOutcome.detail;
      if (testMode === 'stale' || detail.versionStamp !== versionStamp) {
        return { status: 'conflict_stale_object', idempotencyKey: key, objectId: simulationId, objectType: 'budget_simulation', tenantId, safeUserCopy: ACTION_COPY.staleObject };
      }

      if (detail.simulationStatus !== 'ready') {
        return {
          status: 'blocked_by_policy',
          idempotencyKey: key,
          objectId: simulationId,
          objectType: 'budget_simulation',
          tenantId,
          safeUserCopy: detail.blockedReason ?? 'Simulation unavailable. No proposal created.',
        };
      }

      const policyCheck = validatePolicyBeforeSubmit(
        testMode === 'blocked_policy' ? 'blocked' : detail.policyAuthority,
        'design_partner',
        'workflow_mutation',
      );
      if (!policyCheck.ok) {
        return { status: 'blocked_by_policy', idempotencyKey: key, objectId: simulationId, objectType: 'budget_simulation', tenantId, policyAuthority: detail.policyAuthority, safeUserCopy: policyCheck.copy };
      }

      const safety = await checkSubsystemSafetyForExternalAction(tenantId, false, true);
      if (!safety.safe || testMode === 'subsystem_unsafe') {
        return { status: 'subsystem_unsafe', idempotencyKey: key, objectId: simulationId, objectType: 'budget_simulation', tenantId, safeUserCopy: safety.copy ?? ACTION_COPY.subsystemUnsafe };
      }

      const replay = getIdempotencyReplay(key);
      if (replay || testMode === 'replay') {
        return { status: 'replay_rejected', idempotencyKey: key, objectId: simulationId, objectType: 'budget_simulation', tenantId, safeUserCopy: ACTION_COPY.replayRejected };
      }

      if (!markIdempotencyPending(key)) {
        return { status: 'replay_rejected', idempotencyKey: key, objectId: simulationId, objectType: 'budget_simulation', tenantId, safeUserCopy: ACTION_COPY.replayRejected };
      }

      const actionId = createActionId('budget_proposal');
      const auditEventId = createAuditEventId('budget_proposal');
      const proposalId = `prop_${simulationId}`;
      recordIdempotencySuccess(key, actionId, auditEventId);

      return {
        status: 'success',
        idempotencyKey: key,
        objectId: simulationId,
        objectType: 'budget_simulation',
        tenantId,
        actionId,
        auditEventId,
        proposalId,
        approvalState: 'pending_approval',
        policyAuthority: detail.policyAuthority,
        createdAt: new Date().toISOString(),
        safeUserCopy: ACTION_COPY.proposalSuccess(proposalId),
      };
    },
  };
}

let defaultClient: ReturnType<typeof createBudgetProposalClient> | null = null;

export function getDefaultBudgetProposalClient() {
  if (!defaultClient) defaultClient = createBudgetProposalClient();
  return defaultClient;
}

export function resetDefaultBudgetProposalClient(): void {
  defaultClient = null;
}

export function submitBudgetProposal(
  tenantId: string,
  simulationId: string,
  versionStamp: string,
  idempotencyKey?: string,
): Promise<GovernedActionOutcome> {
  return getDefaultBudgetProposalClient().submitBudgetProposal(tenantId, simulationId, versionStamp, idempotencyKey);
}
