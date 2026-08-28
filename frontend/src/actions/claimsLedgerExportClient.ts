import { getCurrentUserRole } from '../governance/governanceStore';
import type { ClaimsFilters } from '../claims/claimsClient';
import { getDefaultClaimsLedgerClient } from '../claims/claimsClient';
import { buildActiveClaimsFilterChips } from '../claims/claimsFilterConfig';
import { ACTION_COPY } from './copy';
import { MAX_EXPORT_PREVIEW_BYTES } from './bounds';
import {
  createActionId,
  createAuditEventId,
  generateIdempotencyKey,
  getIdempotencyReplay,
  markIdempotencyPending,
  recordIdempotencySuccess,
} from './idempotency';
import { hasActionPermission } from './permissions';
import { checkSubsystemSafetyForExternalAction } from './systemSafety';
import type { ClaimsLedgerExportPreview, GovernedActionOutcome } from './types';

export type ClaimsLedgerExportTestMode = 'default' | 'permission_denied' | 'replay' | 'empty';

let testMode: ClaimsLedgerExportTestMode = 'default';

export function setClaimsLedgerExportTestMode(mode: ClaimsLedgerExportTestMode): void {
  testMode = mode;
}

export function resetClaimsLedgerExportTestMode(): void {
  testMode = 'default';
}

function buildFilterSummary(filters: ClaimsFilters): string[] {
  const chips = buildActiveClaimsFilterChips(filters);
  if (chips.length === 0) return ['All claims in tenant scope'];
  return chips.map((chip) => chip.label);
}

export function createClaimsLedgerExportClient() {
  return {
    async buildLedgerExportPreview(
      tenantId: string,
      filters: ClaimsFilters,
    ): Promise<ClaimsLedgerExportPreview | null> {
      const outcome = await getDefaultClaimsLedgerClient().listClaims(tenantId, {
        ...filters,
        offset: 0,
        pageSize: 250,
      });
      if (outcome.kind !== 'loaded' && outcome.kind !== 'partial') return null;

      const claimRefs = outcome.rows.map((row) => row.claimRef);
      const filterSummary = buildFilterSummary(filters);
      const previewBytes = JSON.stringify({ claimRefs, filterSummary, totalCount: outcome.totalCount }).length;

      return {
        claimRefs,
        totalCount: outcome.totalCount,
        filterSummary,
        previewBytes,
        oversize: previewBytes > MAX_EXPORT_PREVIEW_BYTES,
      };
    },

    async exportVerifiedLedgerReport(
      tenantId: string,
      filters: ClaimsFilters,
      idempotencyKey?: string,
    ): Promise<GovernedActionOutcome> {
      const objectId = `ledger:${JSON.stringify(filters)}`;
      const key =
        idempotencyKey ?? generateIdempotencyKey(tenantId, 'claim', objectId, 'export_verified_ledger_report');

      if (testMode === 'permission_denied' || !hasActionPermission(getCurrentUserRole(), 'export_claim_report')) {
        return {
          status: 'permission_denied',
          idempotencyKey: key,
          objectId,
          objectType: 'claim',
          tenantId,
          safeUserCopy: ACTION_COPY.permissionDenied,
        };
      }

      const safety = await checkSubsystemSafetyForExternalAction(tenantId, false, true);
      if (!safety.safe) {
        return {
          status: 'subsystem_unsafe',
          idempotencyKey: key,
          objectId,
          objectType: 'claim',
          tenantId,
          safeUserCopy: safety.copy ?? ACTION_COPY.subsystemUnsafe,
        };
      }

      const preview = await this.buildLedgerExportPreview(tenantId, filters);
      if (!preview || preview.totalCount === 0 || testMode === 'empty') {
        return {
          status: 'artifact_unavailable',
          idempotencyKey: key,
          objectId,
          objectType: 'claim',
          tenantId,
          safeUserCopy: ACTION_COPY.artifactUnavailable,
        };
      }

      if (preview.oversize) {
        return {
          status: 'artifact_unavailable',
          idempotencyKey: key,
          objectId,
          objectType: 'claim',
          tenantId,
          safeUserCopy: ACTION_COPY.exportNoArtifact,
        };
      }

      const replay = getIdempotencyReplay(key);
      if (replay || testMode === 'replay') {
        return {
          status: 'replay_rejected',
          idempotencyKey: key,
          objectId,
          objectType: 'claim',
          tenantId,
          safeUserCopy: ACTION_COPY.replayRejected,
        };
      }

      if (!markIdempotencyPending(key)) {
        return {
          status: 'replay_rejected',
          idempotencyKey: key,
          objectId,
          objectType: 'claim',
          tenantId,
          safeUserCopy: ACTION_COPY.replayRejected,
        };
      }

      const actionId = createActionId('claims_ledger_export');
      const auditEventId = createAuditEventId('claims_ledger_export');
      const artifactRef = `artifact_claims_ledger_${preview.totalCount}`;
      const artifactHash = `art_claims_ledger_${preview.claimRefs.length}`;
      recordIdempotencySuccess(key, actionId, auditEventId);

      return {
        status: 'success',
        idempotencyKey: key,
        objectId,
        objectType: 'claim',
        tenantId,
        actionId,
        auditEventId,
        artifactRef,
        artifactHash,
        createdAt: new Date().toISOString(),
        safeUserCopy: `Verified ledger report exported for ${preview.totalCount} claims. Artifact ${artifactRef}.`,
      };
    },
  };
}

let defaultClient: ReturnType<typeof createClaimsLedgerExportClient> | null = null;

export function getDefaultClaimsLedgerExportClient() {
  if (!defaultClient) defaultClient = createClaimsLedgerExportClient();
  return defaultClient;
}

export function resetDefaultClaimsLedgerExportClient(): void {
  defaultClient = null;
}

export function exportVerifiedLedgerReport(
  tenantId: string,
  filters: ClaimsFilters,
  idempotencyKey?: string,
): Promise<GovernedActionOutcome> {
  return getDefaultClaimsLedgerExportClient().exportVerifiedLedgerReport(tenantId, filters, idempotencyKey);
}
