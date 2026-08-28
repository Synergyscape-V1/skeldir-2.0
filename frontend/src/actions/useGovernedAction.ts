import { useCallback, useEffect, useRef, useState } from 'react';
import type { PolicyAuthorityState } from '../lib/types';
import { ACTION_COPY } from './copy';
import { getActionRegistryEntry, registerActionOutcome } from './actionRegistry';
import type { ActionConsequenceClass } from './policyGate';
import { isPolicyBlockedForAction, requiresConfirmation, validatePolicyBeforeSubmit } from './policyGate';
import type { ActionFlowPhase, GovernedActionOutcome, GovernedObjectType } from './types';

export interface UseGovernedActionOptions {
  tenantId: string;
  objectId: string;
  objectType: GovernedObjectType;
  actionFingerprint: string;
  policyAuthority: PolicyAuthorityState;
  consequence: ActionConsequenceClass;
  permissionOk: boolean;
  permissionDeniedCopy: string;
  subsystemSafe: boolean;
  subsystemCopy?: string;
  requiresConfirm?: boolean;
  onExecute: (idempotencyKey: string) => Promise<GovernedActionOutcome>;
}

function mapOutcomeToPhase(status: GovernedActionOutcome['status']): ActionFlowPhase {
  switch (status) {
    case 'success':
      return 'success';
    case 'replay_rejected':
      return 'replay_rejected';
    case 'signature_failed':
      return 'signature_failed';
    case 'artifact_unavailable':
      return 'artifact_unavailable';
    case 'audit_write_failed':
      return 'audit_write_failed';
    case 'network_error':
      return 'network_error';
    case 'timeout':
      return 'timeout';
    case 'conflict_stale_object':
      return 'stale_object_conflict';
    case 'partial_failure':
      return 'partial_failure';
    case 'blocked_by_policy':
      return 'policy_blocked';
    case 'permission_denied':
      return 'permission_denied';
    case 'scope_denied':
      return 'scope_denied';
    case 'subsystem_unsafe':
      return 'subsystem_unsafe';
    default:
      return 'idle';
  }
}

export function useGovernedAction({
  tenantId,
  objectId,
  objectType,
  actionFingerprint,
  policyAuthority,
  consequence,
  permissionOk,
  permissionDeniedCopy,
  subsystemSafe,
  subsystemCopy,
  requiresConfirm = true,
  onExecute,
}: UseGovernedActionOptions) {
  const stableKey = `idem_${actionFingerprint}`;
  const [phase, setPhase] = useState<ActionFlowPhase>('idle');
  const [outcome, setOutcome] = useState<GovernedActionOutcome | null>(null);
  const [idempotencyKey, setIdempotencyKey] = useState<string | null>(null);
  const pendingRef = useRef(false);

  useEffect(() => {
    const entry = getActionRegistryEntry(actionFingerprint);
    if (!entry) return;
    setIdempotencyKey(entry.idempotencyKey);
    if (entry.status === 'pending') {
      setPhase('pending');
      pendingRef.current = true;
      return;
    }
    if (entry.outcome) {
      setOutcome(entry.outcome);
      setPhase(mapOutcomeToPhase(entry.outcome.status));
    }
  }, [actionFingerprint]);

  const policyCheck = validatePolicyBeforeSubmit(policyAuthority, 'design_partner', consequence);
  const policyBlocked = !policyCheck.ok;

  const disabledReason = !permissionOk
    ? permissionDeniedCopy
    : !subsystemSafe
      ? subsystemCopy ?? 'Trust systems degraded'
      : policyBlocked
        ? policyCheck.ok
          ? undefined
          : policyCheck.copy
        : undefined;

  const disabled = Boolean(disabledReason) || phase === 'pending';

  const baseOutcome = useCallback(
    (status: GovernedActionOutcome['status'], safeUserCopy: string): GovernedActionOutcome => ({
      status,
      idempotencyKey: stableKey,
      objectId,
      objectType,
      tenantId,
      safeUserCopy,
    }),
    [stableKey, objectId, objectType, tenantId],
  );

  const executeAction = useCallback(async () => {
    if (pendingRef.current) return;
    pendingRef.current = true;
    setPhase('pending');
    const key = idempotencyKey ?? stableKey;
    setIdempotencyKey(key);
    try {
      const result = await onExecute(key);
      setOutcome(result);
      registerActionOutcome(actionFingerprint, result);
      setPhase(mapOutcomeToPhase(result.status));
      if (result.status === 'success') {
        setIdempotencyKey(result.idempotencyKey);
      }
    } finally {
      pendingRef.current = false;
    }
  }, [idempotencyKey, stableKey, onExecute, actionFingerprint]);

  const openConfirmation = useCallback(() => {
    if (disabled || pendingRef.current) return;
    if (!permissionOk) {
      const denied = baseOutcome('permission_denied', permissionDeniedCopy);
      setOutcome(denied);
      setPhase('permission_denied');
      registerActionOutcome(actionFingerprint, denied);
      return;
    }
    if (!subsystemSafe) {
      const unsafe = baseOutcome('subsystem_unsafe', subsystemCopy ?? ACTION_COPY.subsystemUnsafe);
      setOutcome(unsafe);
      setPhase('subsystem_unsafe');
      registerActionOutcome(actionFingerprint, unsafe);
      return;
    }
    if (policyBlocked) {
      const blocked = baseOutcome('blocked_by_policy', policyCheck.ok ? ACTION_COPY.policyBlocked : policyCheck.copy);
      setOutcome(blocked);
      setPhase('policy_blocked');
      registerActionOutcome(actionFingerprint, blocked);
      return;
    }
    if (requiresConfirm && requiresConfirmation(policyAuthority, consequence)) {
      setPhase('confirmation_open');
      return;
    }
    void executeAction();
  }, [
    disabled,
    permissionOk,
    subsystemSafe,
    policyBlocked,
    requiresConfirm,
    policyAuthority,
    consequence,
    permissionDeniedCopy,
    subsystemCopy,
    policyCheck,
    baseOutcome,
    actionFingerprint,
    executeAction,
  ]);

  const confirm = useCallback(() => {
    void executeAction();
  }, [executeAction]);

  const cancel = useCallback(() => {
    if (phase === 'confirmation_open') setPhase('idle');
  }, [phase]);

  const reset = useCallback(() => {
    setPhase('idle');
    setOutcome(null);
    setIdempotencyKey(null);
    pendingRef.current = false;
  }, []);

  return {
    phase,
    outcome,
    disabled,
    disabledReason,
    policyBlocked: isPolicyBlockedForAction(policyAuthority, consequence),
    openConfirmation,
    confirm,
    cancel,
    reset,
    executeAction,
    actionFingerprint,
    stableIdempotencyKey: stableKey,
  };
}
