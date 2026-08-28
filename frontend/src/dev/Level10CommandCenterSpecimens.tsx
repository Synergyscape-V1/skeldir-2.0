import { Navigate, MemoryRouter, useSearchParams } from 'react-router-dom';
import { useLayoutEffect, useState } from 'react';
import { createMockSession, createMockTenant } from '../auth/authClient';
import { establishSession, establishTenant, setBootstrapReady } from '../auth/sessionStore';
import { setCurrentUserRole } from '../governance/governanceStore';
import {
  resetCommandCenterTestMode,
  setCommandCenterDelayForTests,
  setCommandCenterHealthStateForTests,
  setCommandCenterSubstrateOverridesForTests,
  setCommandCenterTestMode,
} from '../commandCenter/commandCenterClient';
import type { TrendPoint } from '../commandCenter/types';
import { buildReferenceTrendPoints } from '../components/commandCenter/VerifiedRevenueChart/verifiedRevenueChartGeometry';
import { CommandCenterPage } from '../components/commandCenter/CommandCenterPage/CommandCenterPage';

const FIXTURE_ROUTES: Record<string, string> = {
  'command-center-loaded': '/app',
  'command-center-no-priority': '/app',
  'command-center-kill-switch': '/app',
  'command-center-trust-api-failed': '/app',
  'command-center-trend-unavailable': '/app',
  'command-center-trend-available': '/app',
  'command-center-partial': '/app',
  'command-center-loading-delayed': '/app',
  'command-center-loading-over-8s': '/app',
  'command-center-empty-tenant': '/app',
  'command-center-stale': '/app',
  'command-center-health-degraded': '/app',
  'command-center-integration-attention': '/app',
};

function buildTrendPoints(): TrendPoint[] {
  return buildReferenceTrendPoints();
}

function applyFixture(fixture: string) {
  resetCommandCenterTestMode();
  setCommandCenterDelayForTests(0);
  switch (fixture) {
    case 'command-center-no-priority':
      setCommandCenterTestMode('no_priority');
      break;
    case 'command-center-kill-switch':
      setCommandCenterTestMode('kill_switch');
      break;
    case 'command-center-trust-api-failed':
      setCommandCenterTestMode('trust_api_failed');
      break;
    case 'command-center-trend-unavailable':
      setCommandCenterTestMode('trend_unavailable');
      break;
    case 'command-center-trend-available':
      setCommandCenterSubstrateOverridesForTests({ trendPointsOverride: buildTrendPoints() });
      break;
    case 'command-center-partial':
      setCommandCenterTestMode('partial');
      break;
    case 'command-center-loading-delayed':
      setCommandCenterDelayForTests(2500);
      break;
    case 'command-center-loading-over-8s':
      setCommandCenterDelayForTests(12_000);
      break;
    case 'command-center-empty-tenant':
      break;
    case 'command-center-stale':
      setCommandCenterTestMode('stale');
      break;
    case 'command-center-health-degraded':
      setCommandCenterHealthStateForTests('confidence_degraded');
      break;
    case 'command-center-integration-attention':
      setCommandCenterHealthStateForTests('integration_attention');
      break;
    default:
      break;
  }
}

export function Level10CommandCenterSpecimens() {
  const [params] = useSearchParams();
  const fixture = params.get('fixture') ?? 'command-center-loaded';
  const target = FIXTURE_ROUTES[fixture] ?? '/app';
  const [ready, setReady] = useState(false);

  useLayoutEffect(() => {
    if (fixture === 'command-center-empty-tenant') {
      establishSession(createMockSession(), null);
    } else {
      establishTenant(createMockSession(), createMockTenant());
    }
    setBootstrapReady();
    setCurrentUserRole('owner');
    applyFixture(fixture);
    setReady(true);
  }, [fixture]);

  if (!ready) {
    return <div data-level10-specimens data-level10-specimen-loading />;
  }

  if (fixture === 'command-center-empty-tenant') {
    return (
      <MemoryRouter>
        <CommandCenterPage />
      </MemoryRouter>
    );
  }

  return <Navigate to={target} replace />;
}
