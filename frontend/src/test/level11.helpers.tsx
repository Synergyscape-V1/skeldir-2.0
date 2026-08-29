import { existsSync, readFileSync } from 'node:fs';

import { join } from 'node:path';

import { render, waitFor } from '@testing-library/react';

import userEvent from '@testing-library/user-event';

import { createMemoryRouter } from 'react-router-dom';

import { expect } from 'vitest';

import { AppShellRoutes } from '../app/routes/ShellRoutes';

import { AuthEntryFlow } from '../components/auth/AuthEntryFlow/AuthEntryFlow';

import { PublicRouteNotFoundPage } from '../routeRecovery/PublicRouteNotFoundPage';

import {

  getBillingPortalAttemptCount,

  resetBillingTestState,

  setBillingTestMode,

} from '../billing/billingClient';

import { BILLING_COPY } from '../billing/copy';

import { ROUTE_RECOVERY_COPY } from '../routeRecovery/copy';

import { createMockSession, createMockTenant } from '../auth/authClient';

import {

  establishSession,

  establishTenant,

  resetAuthStateForTests,

  setBootstrapReady,

  clearSession,

} from '../auth/sessionStore';

import { resetGovernanceStateForTests, setCurrentUserRole } from '../governance/governanceStore';

import type { TeamRole } from '../governance/types';

import { renderDetailRouter, setMobileViewport375 } from './level9.helpers';

import { setDesktopViewport1280, resetViewport } from './level10.helpers';



export type Level11ShellRole = TeamRole;



export function seedShellAuth(role: Level11ShellRole = 'owner') {

  establishTenant(createMockSession(), createMockTenant());

  setBootstrapReady();

  setCurrentUserRole(role);

}



export function seedShellAuthWithoutTenant(role: Level11ShellRole = 'owner') {

  establishSession(createMockSession(), null);

  setBootstrapReady();

  setCurrentUserRole(role);

}



export function seedUnauthenticatedShellReady() {

  clearSession();

  setBootstrapReady();

}



export function renderLevel11Shell(initialPath = '/app/settings/billing') {

  const router = createMemoryRouter(

    [

      { path: '/app/*', element: <AppShellRoutes /> },

      { path: '/login', element: <div data-login-page>Login page</div> },

      { path: '/signup', element: <AuthEntryFlow dataRoute="/signup" /> },

    ],

    { initialEntries: [initialPath] },

  );

  return { ...renderDetailRouter(router), router };

}



export function renderPublicApp(initialPath = '/unknown-public-route') {

  const router = createMemoryRouter(

    [{ path: '*', element: <PublicRouteNotFoundPage /> }],

    { initialEntries: [initialPath] },

  );

  return { ...renderDetailRouter(router), router };

}



export function resetLevel11HarnessState() {

  resetAuthStateForTests();

  resetGovernanceStateForTests();

  resetBillingTestState();

  clearSession();

}



export async function waitForBillingLoaded() {

  await waitForBillingState('loaded');

}



export async function waitForBillingState(state: string) {

  await waitFor(() => expect(document.querySelector(`[data-billing-state="${state}"]`)).toBeTruthy());

}



export function assertInvoiceTableBounded() {

  const wrap = document.querySelector('[data-billing-invoice-scroll-wrap]');

  expect(wrap).toBeTruthy();

  expect(document.querySelector('[data-billing-invoices]')).toBeTruthy();

}



export function assertNoShellHorizontalScroll() {

  const shell = document.querySelector('[data-authenticated-app-shell]') as HTMLElement | null;

  if (!shell) return;

  expect(shell.scrollWidth).toBeLessThanOrEqual(shell.clientWidth + 2);

}



export function assertLevel11VisualArtifactsExist() {

  const visualDir = join(process.cwd(), 'evidence', 'Level_11', 'visual');

  const indexPath = join(visualDir, 'visual-artifact-index.json');

  expect(existsSync(indexPath)).toBe(true);

  const index = JSON.parse(readFileSync(indexPath, 'utf8')) as Array<{ file: string }>;

  expect(index.length).toBe(4);

  for (const entry of index) {

    expect(existsSync(join(visualDir, entry.file))).toBe(true);

  }

}



export const ROUTE_PRESERVATION_CASES = [

  { path: '/app/claims/claim_0001', marker: '[data-claim-detail-loaded]' },


  { path: '/app/channels?expand=ch_paid_search__google_ads', marker: '[data-channel-inline-expansion]' },

  { path: '/app/budget/sim_0001', marker: '[data-budget-detail-loaded]' },

  { path: '/app/audit?event_id=aud_001', marker: '[data-audit-ledger-page]' },

  { path: '/app/settings/team', marker: '[data-team-settings-page]' },

  { path: '/app/settings/policy', marker: '[data-policy-settings-page]' },

  { path: '/app/settings/billing', marker: '[data-billing-state="loaded"]' },

  { path: '/app', marker: '[data-command-center-loaded="true"]' },

] as const;



export {

  render,

  waitFor,

  userEvent,

  expect,

  setMobileViewport375,

  setDesktopViewport1280,

  resetViewport,

  BILLING_COPY,

  ROUTE_RECOVERY_COPY,

  getBillingPortalAttemptCount,

  setBillingTestMode,

};

