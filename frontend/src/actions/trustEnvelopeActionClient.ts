import { getCurrentUserRole } from '../governance/governanceStore';
import { getDefaultTrustEnvelopeDetailClient } from '../trustIndex/trustEnvelopeDetailClient';
import { ACTION_COPY } from './copy';
import { MAX_DOWNLOAD_ARTIFACT_BYTES, isOversizePayload } from './bounds';
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
import type { GovernedActionOutcome, TrustEnvelopeExportArtifact } from './types';

export type TrustActionTestMode =
  | 'default'
  | 'replay'
  | 'permission_denied';

let testMode: TrustActionTestMode = 'default';

export function setTrustActionTestMode(mode: TrustActionTestMode): void {
  testMode = mode;
}

export function resetTrustActionTestMode(): void {
  testMode = 'default';
}

export function createTrustEnvelopeActionClient() {
  return {
    async exportArtifact(
      tenantId: string,
      envelopeId: string,
      versionStamp: string,
      idempotencyKey?: string,
    ): Promise<GovernedActionOutcome & { artifact?: TrustEnvelopeExportArtifact }> {
      const key = idempotencyKey ?? generateIdempotencyKey(tenantId, 'trust_envelope', envelopeId, 'export_artifact');

      if (!hasActionPermission(getCurrentUserRole(), 'export_trust_artifact')) {
        return { status: 'permission_denied', idempotencyKey: key, objectId: envelopeId, objectType: 'trust_envelope', tenantId, safeUserCopy: ACTION_COPY.permissionDenied };
      }

      const detailOutcome = await getDefaultTrustEnvelopeDetailClient().getTrustEnvelopeDetail(tenantId, envelopeId);
      if (detailOutcome.kind !== 'loaded') {
        return { status: 'artifact_unavailable', idempotencyKey: key, objectId: envelopeId, objectType: 'trust_envelope', tenantId, safeUserCopy: ACTION_COPY.artifactUnavailable };
      }

      const detail = detailOutcome.detail;
      if (detail.versionStamp !== versionStamp) {
        return { status: 'conflict_stale_object', idempotencyKey: key, objectId: envelopeId, objectType: 'trust_envelope', tenantId, safeUserCopy: ACTION_COPY.staleObject };
      }

      const policyCheck = validatePolicyBeforeSubmit(detail.policyAuthority.state, 'design_partner', 'external_artifact');
      if (!policyCheck.ok) {
        return { status: 'blocked_by_policy', idempotencyKey: key, objectId: envelopeId, objectType: 'trust_envelope', tenantId, policyAuthority: detail.policyAuthority.state, safeUserCopy: policyCheck.copy };
      }

      const safety = await checkSubsystemSafetyForExternalAction(tenantId, false, true);
      if (!safety.safe) {
        return { status: 'subsystem_unsafe', idempotencyKey: key, objectId: envelopeId, objectType: 'trust_envelope', tenantId, safeUserCopy: safety.copy ?? ACTION_COPY.subsystemUnsafe };
      }

      const payloadBytes = 4096;
      const oversize = isOversizePayload(payloadBytes, MAX_DOWNLOAD_ARTIFACT_BYTES);

      const replay = getIdempotencyReplay(key);
      if (replay || testMode === 'replay') {
        return { status: 'replay_rejected', idempotencyKey: key, objectId: envelopeId, objectType: 'trust_envelope', tenantId, safeUserCopy: ACTION_COPY.replayRejected };
      }
      if (!markIdempotencyPending(key)) {
        return { status: 'replay_rejected', idempotencyKey: key, objectId: envelopeId, objectType: 'trust_envelope', tenantId, safeUserCopy: ACTION_COPY.replayRejected };
      }

      const actionId = createActionId('export_artifact');
      const auditEventId = createAuditEventId('export_artifact');
      const artifactRef = `artifact_env_${envelopeId}`;
      recordIdempotencySuccess(key, actionId, auditEventId);

      const artifact: TrustEnvelopeExportArtifact = {
        schemaVersion: 'operator-view-v1',
        canonicalizationVersion: 'n/a',
        semanticTruthHash: '',
        artifactHash: '',
        signatureHash: null,
        keyId: null,
        signatureAlgorithm: null,
        createdAt: new Date().toISOString(),
        auditEventId,
        artifactRef,
        payloadBytes,
        oversize,
      };

      return {
        status: 'success',
        idempotencyKey: key,
        objectId: envelopeId,
        objectType: 'trust_envelope',
        tenantId,
        actionId,
        auditEventId,
        artifactRef,
        createdAt: artifact.createdAt,
        safeUserCopy: oversize
          ? `Artifact ${artifactRef} ready via external handoff. Preview exceeds inline bounds.`
          : `Artifact ${artifactRef} exported. Open ${detail.auditReference} in the Audit Ledger for forensic review.`,
        artifact,
      };
    },
  };
}

let defaultClient: ReturnType<typeof createTrustEnvelopeActionClient> | null = null;

export function getDefaultTrustEnvelopeActionClient() {
  if (!defaultClient) defaultClient = createTrustEnvelopeActionClient();
  return defaultClient;
}

export function resetDefaultTrustEnvelopeActionClient(): void {
  defaultClient = null;
}

export function exportArtifact(
  tenantId: string,
  envelopeId: string,
  versionStamp: string,
  idempotencyKey?: string,
): Promise<GovernedActionOutcome & { artifact?: TrustEnvelopeExportArtifact }> {
  return getDefaultTrustEnvelopeActionClient().exportArtifact(tenantId, envelopeId, versionStamp, idempotencyKey);
}
