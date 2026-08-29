import { getCurrentUserRole } from '../governance/governanceStore';
import { getDefaultClaimDetailClient } from '../claims/claimDetailClient';
import { DETAIL_COPY } from '../detail/copy';
import type { ClaimDetailDTO } from '../detail/types';
import {
  allowsVerifiedExport,
  resolveClaimExecutiveReliability,
} from '../trust/executiveDataReliability';
import { EXECUTIVE_RELIABILITY_COPY } from '../trust/executiveDataReliabilityCopy';
import { ACTION_COPY } from './copy';
import {
  createActionId,
  createAuditEventId,
  generateIdempotencyKey,
  getIdempotencyReplay,
  markIdempotencyPending,
  clearIdempotencyPending,
  recordIdempotencySuccess,
} from './idempotency';
import { hasActionPermission } from './permissions';
import { validatePolicyBeforeSubmit } from './policyGate';
import { checkSubsystemSafetyForExternalAction } from './systemSafety';
import type { ClaimExportPreview, GovernedActionOutcome } from './types';
import { MAX_EXPORT_PREVIEW_BYTES } from './bounds';

export type ClaimExportTestMode =
  | 'default'
  | 'permission_denied'
  | 'cross_tenant'
  | 'replay'
  | 'network_error'
  | 'audit_write_failed'
  | 'subsystem_unsafe'
  | 'timeout'
  | 'partial_failure';

let testMode: ClaimExportTestMode = 'default';
let exportDelayMs = 0;

export function setClaimExportDelayForTests(ms: number): void {
  exportDelayMs = ms;
}

export function setClaimExportTestMode(mode: ClaimExportTestMode): void {
  testMode = mode;
}

export function resetClaimExportTestMode(): void {
  testMode = 'default';
  exportDelayMs = 0;
}

function buildPreview(detail: ClaimDetailDTO): ClaimExportPreview {
  const confidenceSummary =
    detail.confidence.status === 'unavailable'
      ? `Confidence unavailable: ${detail.confidence.reason ?? 'reason not provided'}`
      : `Confidence interval ${detail.confidence.intervalLower}–${detail.confidence.intervalUpper}`;
  const benchmarkSummary =
    detail.benchmark.status === 'unavailable'
      ? `Benchmark unavailable: ${detail.benchmark.reason ?? 'no defensible benchmark'}`
      : `Benchmark ${detail.benchmark.decisionSafeBenchmark} (${detail.benchmark.evidenceClass})`;

  return {
    claimId: detail.claimId,
    claimSource: detail.claimSource,
    claimedRevenueMinor: detail.claimedRevenueMinor.toString(),
    verifiedRevenueMinor: detail.verifiedRevenueMinor.toString(),
    currencyCode: detail.currencyCode,
    discrepancyClass: detail.discrepancyClass,
    attributionModel: detail.attribution.selectedModel,
    modelAssumption: detail.attribution.modelAssumption,
    causalStatus: detail.attribution.causalStatus,
    confidenceSummary,
    benchmarkSummary,
    policyAuthority: detail.policyAuthority,
    auditReference: detail.audit.auditReference,
    incrementalityBoundaryCopy: detail.incrementalityBoundaryCopy,
    authorityLegend: [
      'Platform claim = prior (not verified truth)',
      'Verified revenue = deterministic commerce-backed',
      'Confidence = probabilistic or unavailable',
      'Benchmark = contextual evidence, not truth',
    ],
  };
}

export function createClaimExportClient() {
  return {
    async buildExportPreview(
      tenantId: string,
      claimId: string,
      signal?: AbortSignal,
    ): Promise<{ ok: true; preview: ClaimExportPreview } | { ok: false; outcome: GovernedActionOutcome }> {
      const outcome = await getDefaultClaimDetailClient().getClaimDetail(tenantId, claimId, signal);
      if (outcome.kind !== 'loaded') {
        return {
          ok: false,
          outcome: {
            status: outcome.kind === 'permission_denied' ? 'permission_denied' : 'artifact_unavailable',
            idempotencyKey: generateIdempotencyKey(tenantId, 'claim', claimId, 'preview'),
            objectId: claimId,
            objectType: 'claim',
            tenantId,
            safeUserCopy: outcome.message,
          },
        };
      }
      return { ok: true, preview: buildPreview(outcome.detail) };
    },

    async exportVerifiedReport(
      tenantId: string,
      claimId: string,
      versionStamp: string,
      idempotencyKey?: string,
    ): Promise<GovernedActionOutcome> {
      const key =
        idempotencyKey ?? generateIdempotencyKey(tenantId, 'claim', claimId, 'export_verified_report');

      if (testMode === 'permission_denied' || !hasActionPermission(getCurrentUserRole(), 'export_claim_report')) {
        return {
          status: 'permission_denied',
          idempotencyKey: key,
          objectId: claimId,
          objectType: 'claim',
          tenantId,
          safeUserCopy: ACTION_COPY.permissionDenied,
        };
      }

      const detailOutcome = await getDefaultClaimDetailClient().getClaimDetail(tenantId, claimId);
      if (detailOutcome.kind !== 'loaded') {
        return {
          status: 'artifact_unavailable',
          idempotencyKey: key,
          objectId: claimId,
          objectType: 'claim',
          tenantId,
          safeUserCopy: detailOutcome.message,
        };
      }
      const detail = detailOutcome.detail;

      const reliability = resolveClaimExecutiveReliability(detail);
      if (!allowsVerifiedExport(reliability)) {
        const exportCopy =
          reliability.reliability === 'discrepancy'
            ? EXECUTIVE_RELIABILITY_COPY.permissions.discrepancyExportBlocked
            : EXECUTIVE_RELIABILITY_COPY.permissions.exportBlocked;
        return {
          status: 'blocked_by_policy',
          idempotencyKey: key,
          objectId: claimId,
          objectType: 'claim',
          tenantId,
          policyAuthority: detail.policyAuthority,
          safeUserCopy: exportCopy,
        };
      }

      if (testMode === 'cross_tenant' || detail.tenantId !== tenantId) {
        return {
          status: 'scope_denied',
          idempotencyKey: key,
          objectId: claimId,
          objectType: 'claim',
          tenantId,
          safeUserCopy: ACTION_COPY.scopeDenied,
        };
      }

      if (detail.versionStamp !== versionStamp) {
        return {
          status: 'conflict_stale_object',
          idempotencyKey: key,
          objectId: claimId,
          objectType: 'claim',
          tenantId,
          safeUserCopy: ACTION_COPY.staleObject,
        };
      }

      const policyCheck = validatePolicyBeforeSubmit(detail.policyAuthority, 'design_partner', 'external_artifact');
      if (!policyCheck.ok) {
        return {
          status: 'blocked_by_policy',
          idempotencyKey: key,
          objectId: claimId,
          objectType: 'claim',
          tenantId,
          policyAuthority: detail.policyAuthority,
          safeUserCopy: policyCheck.copy,
        };
      }

      const safety = await checkSubsystemSafetyForExternalAction(tenantId, false, true);
      if (!safety.safe || testMode === 'subsystem_unsafe') {
        return {
          status: 'subsystem_unsafe',
          idempotencyKey: key,
          objectId: claimId,
          objectType: 'claim',
          tenantId,
          safeUserCopy: safety.copy ?? ACTION_COPY.subsystemUnsafe,
        };
      }

      const replay = getIdempotencyReplay(key);
      if (replay || testMode === 'replay') {
        return {
          status: 'replay_rejected',
          idempotencyKey: key,
          objectId: claimId,
          objectType: 'claim',
          tenantId,
          actionId: replay?.actionId,
          auditEventId: replay?.auditEventId,
          safeUserCopy: ACTION_COPY.replayRejected,
        };
      }

      if (!markIdempotencyPending(key)) {
        return {
          status: 'replay_rejected',
          idempotencyKey: key,
          objectId: claimId,
          objectType: 'claim',
          tenantId,
          safeUserCopy: ACTION_COPY.replayRejected,
        };
      }

      if (exportDelayMs > 0) {
        await new Promise((resolve) => setTimeout(resolve, exportDelayMs));
      }

      if (testMode === 'network_error') {
        clearIdempotencyPending(key);
        return {
          status: 'network_error',
          idempotencyKey: key,
          objectId: claimId,
          objectType: 'claim',
          tenantId,
          safeUserCopy: ACTION_COPY.networkError,
        };
      }

      if (testMode === 'timeout') {
        clearIdempotencyPending(key);
        return {
          status: 'timeout',
          idempotencyKey: key,
          objectId: claimId,
          objectType: 'claim',
          tenantId,
          safeUserCopy: ACTION_COPY.timeout,
        };
      }

      if (testMode === 'audit_write_failed') {
        clearIdempotencyPending(key);
        return {
          status: 'audit_write_failed',
          idempotencyKey: key,
          objectId: claimId,
          objectType: 'claim',
          tenantId,
          safeUserCopy: ACTION_COPY.auditWriteFailed,
        };
      }

      const preview = buildPreview(detail);
      const previewBytes = new TextEncoder().encode(JSON.stringify(preview)).length;
      if (previewBytes > MAX_EXPORT_PREVIEW_BYTES) {
        clearIdempotencyPending(key);
        return {
          status: 'artifact_unavailable',
          idempotencyKey: key,
          objectId: claimId,
          objectType: 'claim',
          tenantId,
          safeUserCopy: 'Export preview exceeds safe bounds.',
        };
      }

      const actionId = createActionId('claim_export');
      const auditEventId = createAuditEventId('claim_export');
      const artifactRef = `artifact_claim_${claimId}`;

      if (testMode === 'partial_failure') {
        clearIdempotencyPending(key);
        return {
          status: 'partial_failure',
          idempotencyKey: key,
          objectId: claimId,
          objectType: 'claim',
          tenantId,
          actionId,
          auditEventId,
          safeUserCopy: ACTION_COPY.partialFailure,
        };
      }

      const successOutcome: GovernedActionOutcome = {
        status: 'success',
        idempotencyKey: key,
        objectId: claimId,
        objectType: 'claim',
        tenantId,
        actionId,
        auditEventId,
        artifactRef,
        policyAuthority: detail.policyAuthority,
        createdAt: new Date().toISOString(),
        safeUserCopy: `Verified report exported. Artifact ${artifactRef}. Audit ${detail.audit.auditReference}. ${DETAIL_COPY.incrementalityBoundary}`,
      };
      recordIdempotencySuccess(key, actionId, auditEventId, successOutcome);

      return successOutcome;
    },
  };
}

let defaultClient: ReturnType<typeof createClaimExportClient> | null = null;

export function getDefaultClaimExportClient() {
  if (!defaultClient) defaultClient = createClaimExportClient();
  return defaultClient;
}

export function resetDefaultClaimExportClient(): void {
  defaultClient = null;
}

export function exportVerifiedReport(
  tenantId: string,
  claimId: string,
  versionStamp: string,
  idempotencyKey?: string,
): Promise<GovernedActionOutcome> {
  return getDefaultClaimExportClient().exportVerifiedReport(tenantId, claimId, versionStamp, idempotencyKey);
}
