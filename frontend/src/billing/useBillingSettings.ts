import { useCallback, useEffect, useState } from 'react';
import { getAuthState } from '../auth/sessionStore';
import { getCurrentUserRole } from '../governance/governanceStore';
import {
  fetchBillingSummary,
  initiateManageBilling,
  resetBillingTestState,
} from './billingClient';
import { canManageBilling, canViewBilling } from './permissions';
import type { BillingFetchOutcome, BillingPortalOutcome } from './types';

export function useBillingSettings() {
  const { tenant } = getAuthState();
  const role = getCurrentUserRole();
  const [outcome, setOutcome] = useState<BillingFetchOutcome>({ kind: 'loading' });
  const [portalPending, setPortalPending] = useState(false);
  const [portalError, setPortalError] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const canView = canViewBilling(role);
  const canManage = canManageBilling(role);

  const load = useCallback(async () => {
    if (!tenant) {
      setOutcome({ kind: 'permission_denied' });
      return;
    }
    if (!canView) {
      setOutcome({ kind: 'permission_denied' });
      return;
    }
    setOutcome({ kind: 'loading' });
    const result = await fetchBillingSummary(tenant.tenantId);
    setOutcome(result);
  }, [tenant, canView]);

  useEffect(() => {
    void load();
  }, [load]);

  const requestManageBilling = () => {
    if (!canManage) return;
    setPortalError(null);
    setConfirmOpen(true);
  };

  const confirmManageBilling = async (): Promise<BillingPortalOutcome> => {
    if (!canManage) {
      return { kind: 'permission_denied' };
    }
    setPortalPending(true);
    setPortalError(null);
    const result = await initiateManageBilling();
    setPortalPending(false);
    setConfirmOpen(false);
    if (result.kind === 'network_error') {
      setPortalError('network_error');
    } else if (result.kind === 'portal_unavailable') {
      setPortalError('portal_unavailable');
    } else if (result.kind === 'already_pending') {
      setPortalError('already_pending');
    }
    return result;
  };

  const cancelManageBilling = () => {
    setConfirmOpen(false);
  };

  return {
    outcome,
    summary: outcome.kind === 'loaded' ? outcome.summary : null,
    canView,
    canManage,
    portalPending,
    portalError,
    confirmOpen,
    requestManageBilling,
    confirmManageBilling,
    cancelManageBilling,
    reload: load,
  };
}

export { resetBillingTestState };
