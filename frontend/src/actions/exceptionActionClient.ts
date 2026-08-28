import { getCurrentUserRole } from '../governance/governanceStore';
import { getDefaultExceptionDetailClient } from '../exceptions/exceptionDetailClient';
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
import type { ExceptionActionKind, GovernedActionOutcome } from './types';

export type ExceptionActionTestMode =
  | 'default'
  | 'permission_denied'
  | 'replay'
  | 'stale'
  | 'wrong_exception'
  | 'audit_write_failed';

let testMode: ExceptionActionTestMode = 'default';
let policyOverride: 'approval_required' | 'blocked' | null = null;

export function setExceptionActionTestMode(mode: ExceptionActionTestMode): void {
  testMode = mode;
}

export function setExceptionPolicyOverrideForTests(policy: 'approval_required' | 'blocked' | null): void {
  policyOverride = policy;
}

export function resetExceptionActionTestMode(): void {
  testMode = 'default';
  policyOverride = null;
}

const ACTION_COPY_MAP: Record<ExceptionActionKind, { label: string; confirm: string }> = {
  acknowledge: {
    label: 'Acknowledge',
    confirm: 'Acknowledge this exception for review tracking? No financial truth will change.',
  },
  request_more_evidence: {
    label: 'Request more evidence',
    confirm: 'Request additional evidence for this exception?',
  },
  mark_disputed: {
    label: 'Mark disputed',
    confirm: 'Mark this exception as disputed? This updates review state only.',
  },
  suppress_similar: {
    label: 'Suppress similar low-risk alerts',
    confirm: ACTION_COPY.suppressScope,
  },
  create_proposal: {
    label: 'Create proposal',
    confirm: 'Create a governed proposal from this exception? No spend will be executed.',
  },
};

export function createExceptionActionClient() {
  return {
    getActionCopy(kind: ExceptionActionKind) {
      return ACTION_COPY_MAP[kind];
    },

    async performExceptionAction(
      tenantId: string,
      exceptionId: string,
      kind: ExceptionActionKind,
      versionStamp: string,
      idempotencyKey?: string,
    ): Promise<GovernedActionOutcome> {
      const key =
        idempotencyKey ?? generateIdempotencyKey(tenantId, 'exception', exceptionId, kind);

      if (testMode === 'permission_denied' || !hasActionPermission(getCurrentUserRole(), 'perform_exception_action')) {
        return { status: 'permission_denied', idempotencyKey: key, objectId: exceptionId, objectType: 'exception', tenantId, safeUserCopy: ACTION_COPY.permissionDenied };
      }

      if (testMode === 'wrong_exception') {
        return { status: 'conflict_stale_object', idempotencyKey: key, objectId: exceptionId, objectType: 'exception', tenantId, safeUserCopy: 'Exception identity mismatch.' };
      }

      const detailOutcome = await getDefaultExceptionDetailClient().getExceptionDetail(tenantId, exceptionId);
      if (detailOutcome.kind !== 'loaded') {
        return { status: 'artifact_unavailable', idempotencyKey: key, objectId: exceptionId, objectType: 'exception', tenantId, safeUserCopy: ACTION_COPY.artifactUnavailable };
      }

      const detail = detailOutcome.detail;
      if (testMode === 'stale' || detail.versionStamp !== versionStamp) {
        return { status: 'conflict_stale_object', idempotencyKey: key, objectId: exceptionId, objectType: 'exception', tenantId, safeUserCopy: ACTION_COPY.staleObject };
      }

      const policy = policyOverride ?? detail.policyAuthority;
      const consequence = kind === 'create_proposal' ? 'workflow_mutation' : 'workflow_mutation';
      const policyCheck = validatePolicyBeforeSubmit(policy, 'design_partner', consequence);
      if (!policyCheck.ok) {
        return { status: 'blocked_by_policy', idempotencyKey: key, objectId: exceptionId, objectType: 'exception', tenantId, policyAuthority: policy, safeUserCopy: policyCheck.copy };
      }

      const safety = await checkSubsystemSafetyForExternalAction(tenantId, false, true);
      if (!safety.safe) {
        return { status: 'subsystem_unsafe', idempotencyKey: key, objectId: exceptionId, objectType: 'exception', tenantId, safeUserCopy: safety.copy ?? ACTION_COPY.subsystemUnsafe };
      }

      const replay = getIdempotencyReplay(key);
      if (replay || testMode === 'replay') {
        return { status: 'replay_rejected', idempotencyKey: key, objectId: exceptionId, objectType: 'exception', tenantId, safeUserCopy: ACTION_COPY.replayRejected };
      }

      if (!markIdempotencyPending(key)) {
        return { status: 'replay_rejected', idempotencyKey: key, objectId: exceptionId, objectType: 'exception', tenantId, safeUserCopy: ACTION_COPY.replayRejected };
      }

      if (testMode === 'audit_write_failed') {
        clearIdempotencyPending(key);
        return { status: 'audit_write_failed', idempotencyKey: key, objectId: exceptionId, objectType: 'exception', tenantId, safeUserCopy: ACTION_COPY.auditWriteFailed };
      }

      const actionId = createActionId(`exc_${kind}`);
      const auditEventId = createAuditEventId(`exc_${kind}`);
      recordIdempotencySuccess(key, actionId, auditEventId);

      const proposalId = kind === 'create_proposal' ? `prop_exc_${exceptionId}` : undefined;

      return {
        status: 'success',
        idempotencyKey: key,
        objectId: exceptionId,
        objectType: 'exception',
        tenantId,
        actionId,
        auditEventId,
        proposalId: proposalId ?? null,
        approvalState: kind === 'create_proposal' ? 'pending_approval' : null,
        policyAuthority: policy,
        createdAt: new Date().toISOString(),
        safeUserCopy: `${ACTION_COPY_MAP[kind].label} completed. Action ${actionId}. Audit ${auditEventId}.`,
      };
    },
  };
}

let defaultClient: ReturnType<typeof createExceptionActionClient> | null = null;

export function getDefaultExceptionActionClient() {
  if (!defaultClient) defaultClient = createExceptionActionClient();
  return defaultClient;
}

export function resetDefaultExceptionActionClient(): void {
  defaultClient = null;
}

export function acknowledgeException(
  tenantId: string,
  exceptionId: string,
  versionStamp: string,
  idempotencyKey?: string,
): Promise<GovernedActionOutcome> {
  return getDefaultExceptionActionClient().performExceptionAction(tenantId, exceptionId, 'acknowledge', versionStamp, idempotencyKey);
}

export function requestMoreEvidence(
  tenantId: string,
  exceptionId: string,
  versionStamp: string,
  idempotencyKey?: string,
): Promise<GovernedActionOutcome> {
  return getDefaultExceptionActionClient().performExceptionAction(tenantId, exceptionId, 'request_more_evidence', versionStamp, idempotencyKey);
}

export function markDisputed(
  tenantId: string,
  exceptionId: string,
  versionStamp: string,
  idempotencyKey?: string,
): Promise<GovernedActionOutcome> {
  return getDefaultExceptionActionClient().performExceptionAction(tenantId, exceptionId, 'mark_disputed', versionStamp, idempotencyKey);
}

export function suppressSimilarAlerts(
  tenantId: string,
  exceptionId: string,
  versionStamp: string,
  idempotencyKey?: string,
): Promise<GovernedActionOutcome> {
  return getDefaultExceptionActionClient().performExceptionAction(tenantId, exceptionId, 'suppress_similar', versionStamp, idempotencyKey);
}

export function createProposal(
  tenantId: string,
  exceptionId: string,
  versionStamp: string,
  idempotencyKey?: string,
): Promise<GovernedActionOutcome> {
  return getDefaultExceptionActionClient().performExceptionAction(tenantId, exceptionId, 'create_proposal', versionStamp, idempotencyKey);
}
