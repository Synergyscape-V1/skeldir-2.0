import { useCallback, useEffect, useState } from 'react';
import type { PolicyAuthorityState } from '../lib/types';
import { getAuthState } from '../auth/sessionStore';
import { getDefaultGovernanceClient } from './governanceClient';
import { isGovernanceError, mapGovernanceError } from './governanceOutcomeMapping';
import { getCurrentUserRole } from './governanceStore';
import { canConfigurePolicy } from './permissions';
import type { AutoExecuteConstraints, PolicyActionCategory, PolicySettings } from './types';

export function usePolicySettings() {
  const [policy, setPolicy] = useState<PolicySettings | undefined>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | undefined>();
  const [permissionDenied, setPermissionDenied] = useState(false);
  const [configureCategory, setConfigureCategory] = useState<PolicyActionCategory | undefined>();
  const [savePending, setSavePending] = useState(false);
  const [saveFailed, setSaveFailed] = useState(false);

  const refresh = useCallback(async () => {
    const { tenant } = getAuthState();
    if (!tenant) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(undefined);
    setPermissionDenied(false);
    try {
      const client = getDefaultGovernanceClient();
      const outcome = await client.getPolicy(tenant.tenantId);
      if (isGovernanceError(outcome)) {
        if (outcome.kind === 'permission_denied') setPermissionDenied(true);
        setError(mapGovernanceError(outcome));
        return;
      }
      if (outcome.kind === 'policy_loaded') {
        setPolicy(outcome.policy);
      }
    } catch {
      setError('Policy service unavailable. Try again shortly.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const saveCategory = useCallback(
    async (
      category: PolicyActionCategory,
      authority: PolicyAuthorityState,
      constraints?: AutoExecuteConstraints,
    ) => {
      if (!canConfigurePolicy(getCurrentUserRole())) {
        setPermissionDenied(true);
        return { ok: false as const };
      }
      const { tenant } = getAuthState();
      if (!tenant) return { ok: false as const };
      setSavePending(true);
      setSaveFailed(false);
      const client = getDefaultGovernanceClient();
      const outcome = await client.savePolicyCategory(
        tenant.tenantId,
        category,
        authority,
        constraints,
      );
      setSavePending(false);
      if (isGovernanceError(outcome)) {
        setSaveFailed(true);
        setError(mapGovernanceError(outcome));
        return { ok: false as const, error: mapGovernanceError(outcome) };
      }
      if (outcome.kind === 'policy_saved') {
        setPolicy(outcome.policy);
        setConfigureCategory(undefined);
      }
      return { ok: true as const };
    },
    [],
  );

  return {
    policy,
    loading,
    error,
    permissionDenied,
    configureCategory,
    setConfigureCategory,
    savePending,
    saveFailed,
    canConfigure: canConfigurePolicy(getCurrentUserRole()),
    refresh,
    saveCategory,
  };
}
