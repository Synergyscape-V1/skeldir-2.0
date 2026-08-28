import { Navigate, useSearchParams } from 'react-router-dom';
import { useLayoutEffect, useState } from 'react';
import { createMockSession, createMockTenant } from '../auth/authClient';
import { establishTenant, setBootstrapReady } from '../auth/sessionStore';
import { setCurrentUserRole } from '../governance/governanceStore';

const FIXTURE_ROUTES: Record<string, string> = {
  'claim-detail-loaded': '/app/claims/claim_0001',
  'claim-detail-not-found': '/app/claims/invalid_id',
  'trust-detail-loaded': '/app/claims/claim_0001?trustEnvelope=env_0001',
  'channel-detail-loaded': '/app/channels?expand=ch_paid_search__google_ads',
  'budget-detail-loaded': '/app/budget/sim_0001',
  'exceptions-drawer': '/app/exceptions',
  'level9-action-flows': '/app/claims/claim_0001',
  'level9-trust-actions': '/app/claims/claim_0001?trustEnvelope=env_0001',
  'level9-audit-export': '/app/audit',
};

export function Level8LedgerSpecimens() {
  const [params] = useSearchParams();
  const fixture = params.get('fixture') ?? 'claim-detail-loaded';
  const target = FIXTURE_ROUTES[fixture] ?? FIXTURE_ROUTES['claim-detail-loaded'];
  const [ready, setReady] = useState(false);

  useLayoutEffect(() => {
    establishTenant(createMockSession(), createMockTenant());
    setBootstrapReady();
    setCurrentUserRole('owner');
    setReady(true);
  }, []);

  if (!ready) {
    return <div data-level8-specimens data-level8-specimen-loading />;
  }

  return <Navigate to={target} replace />;
}
