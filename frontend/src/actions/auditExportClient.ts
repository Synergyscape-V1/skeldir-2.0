import { getCurrentUserRole } from '../governance/governanceStore';
import { getDefaultOperationalAuditClient } from '../operationalAudit/operationalAuditClient';
import type { AuditFilters } from '../operationalAudit/types';
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
import type { AuditReconstructionPreview, GovernedActionOutcome } from './types';

export type AuditExportTestMode =
  | 'default'
  | 'invalid_signature'
  | 'corrupted_artifact'
  | 'access_denied'
  | 'permission_denied'
  | 'replay';

let testMode: AuditExportTestMode = 'default';

export function setAuditExportTestMode(mode: AuditExportTestMode): void {
  testMode = mode;
}

export function resetAuditExportTestMode(): void {
  testMode = 'default';
}

const REDACTED_FIELDS = [
  'email addresses',
  'IP addresses',
  'raw headers',
  'user agents',
  'access tokens',
  'raw webhook payloads',
  'raw payment payloads',
];

export function createAuditExportClient() {
  return {
    async buildReconstructionPreview(
      tenantId: string,
      filters: AuditFilters,
    ): Promise<AuditReconstructionPreview | null> {
      const outcome = await getDefaultOperationalAuditClient().listAuditEvents(tenantId, filters);
      if (outcome.kind !== 'audit_loaded') return null;
      const eventIds = outcome.events.map((e) => e.eventId);
      const hashChain = outcome.events.map((e) => `hash_${e.eventId}`);
      const preview = {
        eventIds,
        hashChain,
        redactionSummary: REDACTED_FIELDS.map((f) => `Excluded: ${f}`),
        previewBytes: JSON.stringify({ eventIds, hashChain }).length,
        oversize: false,
      };
      preview.oversize = preview.previewBytes > MAX_EXPORT_PREVIEW_BYTES;
      return preview;
    },

    async exportAuditReconstruction(
      tenantId: string,
      filters: AuditFilters,
      selectedEventId: string | null,
      idempotencyKey?: string,
    ): Promise<GovernedActionOutcome> {
      const objectId = selectedEventId ?? 'filtered_range';
      const key =
        idempotencyKey ?? generateIdempotencyKey(tenantId, 'audit_event', objectId, 'export_reconstruction');

      if (testMode === 'permission_denied' || !hasActionPermission(getCurrentUserRole(), 'export_audit_reconstruction')) {
        return { status: 'permission_denied', idempotencyKey: key, objectId, objectType: 'audit_event', tenantId, safeUserCopy: ACTION_COPY.permissionDenied };
      }

      if (testMode === 'access_denied') {
        return { status: 'permission_denied', idempotencyKey: key, objectId, objectType: 'audit_event', tenantId, safeUserCopy: 'Access denied for audit export.' };
      }

      if (testMode === 'invalid_signature') {
        return { status: 'signature_failed', idempotencyKey: key, objectId, objectType: 'audit_event', tenantId, safeUserCopy: 'Invalid signature blocks audit export JSON exposure.' };
      }

      if (testMode === 'corrupted_artifact') {
        return { status: 'artifact_unavailable', idempotencyKey: key, objectId, objectType: 'audit_event', tenantId, safeUserCopy: 'Corrupted artifact cannot be exported.' };
      }

      const safety = await checkSubsystemSafetyForExternalAction(tenantId, true, true);
      if (!safety.safe) {
        return { status: 'subsystem_unsafe', idempotencyKey: key, objectId, objectType: 'audit_event', tenantId, safeUserCopy: safety.copy ?? ACTION_COPY.subsystemUnsafe };
      }

      const preview = await this.buildReconstructionPreview(tenantId, filters);
      if (!preview || preview.eventIds.length === 0) {
        return { status: 'artifact_unavailable', idempotencyKey: key, objectId, objectType: 'audit_event', tenantId, safeUserCopy: ACTION_COPY.artifactUnavailable };
      }

      const replay = getIdempotencyReplay(key);
      if (replay || testMode === 'replay') {
        return { status: 'replay_rejected', idempotencyKey: key, objectId, objectType: 'audit_event', tenantId, safeUserCopy: ACTION_COPY.replayRejected };
      }

      if (!markIdempotencyPending(key)) {
        return { status: 'replay_rejected', idempotencyKey: key, objectId, objectType: 'audit_event', tenantId, safeUserCopy: ACTION_COPY.replayRejected };
      }

      const actionId = createActionId('audit_export');
      const auditEventId = createAuditEventId('audit_export');
      const artifactRef = `artifact_audit_${objectId}`;
      const artifactHash = `art_audit_${objectId}`;
      recordIdempotencySuccess(key, actionId, auditEventId);

      return {
        status: 'success',
        idempotencyKey: key,
        objectId,
        objectType: 'audit_event',
        tenantId,
        actionId,
        auditEventId,
        artifactRef,
        artifactHash,
        createdAt: new Date().toISOString(),
        safeUserCopy: `Audit reconstruction exported. Redacted fields: ${REDACTED_FIELDS.length}. Artifact ${artifactRef}.`,
      };
    },
  };
}

let defaultClient: ReturnType<typeof createAuditExportClient> | null = null;

export function getDefaultAuditExportClient() {
  if (!defaultClient) defaultClient = createAuditExportClient();
  return defaultClient;
}

export function resetDefaultAuditExportClient(): void {
  defaultClient = null;
}

export function exportAuditReconstruction(
  tenantId: string,
  filters: AuditFilters,
  selectedEventId: string | null,
  idempotencyKey?: string,
): Promise<GovernedActionOutcome> {
  return getDefaultAuditExportClient().exportAuditReconstruction(tenantId, filters, selectedEventId, idempotencyKey);
}
