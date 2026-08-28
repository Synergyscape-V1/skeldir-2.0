import { Navigate, useSearchParams } from 'react-router-dom';

import { useLayoutEffect, useState } from 'react';

import { createMockSession, createMockTenant } from '../auth/authClient';

import { establishTenant, setBootstrapReady } from '../auth/sessionStore';

import { setCurrentUserRole } from '../governance/governanceStore';

import { resetBillingTestState } from '../billing/billingClient';



const FIXTURE_ROUTES: Record<string, string> = {

  'billing-loaded': '/app/settings/billing',

  'route-recovery': '/app/__level11_unknown_route_fixture__',

};



export function Level11LaunchParitySpecimens() {

  const [params] = useSearchParams();

  const fixture = params.get('fixture') ?? 'billing-loaded';

  const target = FIXTURE_ROUTES[fixture] ?? FIXTURE_ROUTES['billing-loaded'];

  const [ready, setReady] = useState(false);



  useLayoutEffect(() => {

    establishTenant(createMockSession(), createMockTenant());

    setBootstrapReady();

    setCurrentUserRole('owner');

    resetBillingTestState();

    setReady(true);

  }, []);



  if (!ready) {

    return <div data-level11-specimens data-level11-specimen-loading />;

  }



  return <Navigate to={target} replace />;

}

