import { readFileSync } from 'node:fs';

import { join } from 'node:path';

import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';

import { screen, waitFor } from '@testing-library/react';

import userEvent from '@testing-library/user-event';

import {

  assertLevel11ComponentsExist,

  runLevel11IntegrityProbes,

  runLevel11NegativeScopeScan,

  runLevel11SabotageProbes,

  runLevel11SourceIntegrityProbes,

  runLevel11SourceSabotageProbes,

} from '../audit/level11NegativeScopeScan';

import { runLevel10NegativeScopeScan } from '../audit/level10NegativeScopeScan';

import { runPrivacyScan } from '../audit/privacyScan';

import { runSecretScan } from '../audit/secretScan';

import { resolveSafeRedirect } from '../auth/redirectGuard';

import {

  getBillingPortalAttemptCount,

  resetBillingTestState,

  setBillingTestMode,

} from '../billing/billingClient';

import {

  BILLING_COPY,

  ROUTE_RECOVERY_COPY,

  ROUTE_PRESERVATION_CASES,

  assertInvoiceTableBounded,

  assertLevel11VisualArtifactsExist,

  assertNoShellHorizontalScroll,

  renderLevel11Shell,

  renderPublicApp,

  resetLevel11HarnessState,

  seedShellAuth,

  seedShellAuthWithoutTenant,

  seedUnauthenticatedShellReady,

  setDesktopViewport1280,

  setMobileViewport375,

  resetViewport,

  waitForBillingLoaded,

  waitForBillingState,

} from './level11.helpers';

beforeEach(() => {

  vi.useRealTimers();

  resetLevel11HarnessState();

});



afterEach(() => {

  resetViewport();

});



describe('Level 11 Harness — Scope and regression', () => {

  it('Level 10 scope scan still passes', () => {

    expect(runLevel10NegativeScopeScan().violations).toEqual([]);

  });



  it('Level 11 scope scan passes', () => {

    expect(runLevel11NegativeScopeScan().violations).toEqual([]);

  });



  it('Level 11 components and markers exist', () => {

    expect(assertLevel11ComponentsExist()).toEqual({ ok: true, missing: [] });

  });



  it('Level 11 integrity probes pass', () => {

    const probes = runLevel11IntegrityProbes();

    const sourceProbes = runLevel11SourceIntegrityProbes();

    expect(probes.every((p) => p.ok)).toBe(true);

    expect(sourceProbes.every((p) => p.ok)).toBe(true);

  });



  it('privacy and secret scans pass', () => {

    expect(runPrivacyScan().violations).toEqual([]);

    expect(runSecretScan().violations).toEqual([]);

  });



  it('visual artifact index and PNG files exist on disk', () => {

    assertLevel11VisualArtifactsExist();

  });

});



describe('Level 11 Harness — billing activation and navigation', () => {

  it('renders billing page for owner with session and tenant', async () => {

    seedShellAuth('owner');

    renderLevel11Shell('/app/settings/billing');

    await waitForBillingLoaded();

    expect(document.querySelector('[data-billing-page]')).toBeTruthy();

  });



  it('billing reachable from Settings subnav', async () => {

    seedShellAuth('owner');

    renderLevel11Shell('/app/settings/team');

    const billingLink = document.querySelector('[data-settings-billing-link]');

    expect(billingLink?.getAttribute('href')).toBe('/app/settings/billing');

  });



  it('missing session billing route redirects to login', async () => {

    seedUnauthenticatedShellReady();

    const { router } = renderLevel11Shell('/app/settings/billing');

    await waitFor(() => expect(router.state.location.pathname).toBe('/login'));

    expect(document.querySelector('[data-login-page]')).toBeTruthy();

  });



  it('missing tenant billing route redirects to workspace creation', async () => {

    seedShellAuthWithoutTenant('owner');

    const { router } = renderLevel11Shell('/app/settings/billing');

    await waitFor(() => expect(router.state.location.pathname).toBe('/signup'));

    await waitFor(() => expect(document.querySelector('[data-create-organization-modal]')).toBeTruthy());

  });



  it('redirect guard resolves billing alias', () => {

    expect(

      resolveSafeRedirect('/settings/billing', { hasSession: true, hasTenant: true }, '/app'),

    ).toEqual({ ok: true, path: '/app/settings/billing' });

  });



  it('mobile billing route reachable at 375px', async () => {

    setMobileViewport375();

    seedShellAuth('owner');

    renderLevel11Shell('/app/settings/billing');

    await waitForBillingLoaded();

    expect(document.querySelector('[data-billing-page]')).toBeTruthy();

  });

});



describe('Level 11 Harness — billing commercial semantics', () => {

  it('renders trust boundary copy without AuthorityBadge', async () => {

    seedShellAuth('owner');

    renderLevel11Shell('/app/settings/billing');

    await waitForBillingLoaded();

    expect(document.querySelector('[data-billing-trust-boundary]')).toBeTruthy();

    expect(screen.getByText(/Billing does not create verified revenue/i)).toBeInTheDocument();

    expect(document.querySelector('[data-authority-badge]')).toBeNull();

  });

});



describe('Level 11 Harness — billing action-state matrix', () => {

  it('permission_denied state mounted', async () => {

    setBillingTestMode('permission_denied');

    seedShellAuth('owner');

    renderLevel11Shell('/app/settings/billing');

    await waitForBillingState('permission_denied');

    expect(screen.getByText(BILLING_COPY.permissionDenied)).toBeInTheDocument();

  });



  it('loading state mounted', async () => {

    setBillingTestMode('loading');

    seedShellAuth('owner');

    renderLevel11Shell('/app/settings/billing');

    await waitForBillingState('loading');

    expect(document.querySelector('[data-billing-state="loading"]')).toBeTruthy();

    expect(document.querySelector('[aria-busy="true"]')).toBeTruthy();

  });



  it('empty invoice/payment state mounted', async () => {

    setBillingTestMode('empty');

    seedShellAuth('owner');

    renderLevel11Shell('/app/settings/billing');

    await waitForBillingState('empty');

    expect(screen.getByText(BILLING_COPY.invoicesEmpty)).toBeInTheDocument();

  });



  it('confirmation modal opens on manage billing', async () => {

    seedShellAuth('owner');

    const user = userEvent.setup();

    renderLevel11Shell('/app/settings/billing');

    await waitForBillingLoaded();

    await user.click(screen.getByRole('button', { name: BILLING_COPY.manageBilling }));

    expect(screen.getByText(BILLING_COPY.manageBillingConfirmTitle)).toBeInTheDocument();

    expect(document.querySelector('[data-billing-portal-confirm]')).toBeTruthy();

  });



  it('external portal hint copy mounted', async () => {

    seedShellAuth('owner');

    renderLevel11Shell('/app/settings/billing');

    await waitForBillingLoaded();

    expect(screen.getByText(BILLING_COPY.manageBillingExternalHint)).toBeInTheDocument();

  });



  it('pending aria-busy on portal confirm', async () => {

    seedShellAuth('owner');

    const user = userEvent.setup();

    renderLevel11Shell('/app/settings/billing');

    await waitForBillingLoaded();

    await user.click(screen.getByRole('button', { name: BILLING_COPY.manageBilling }));

    const confirm = await screen.findByRole('button', { name: BILLING_COPY.manageBillingConfirmAction });

    await user.click(confirm);

    await waitFor(() => {

      const busy =

        confirm.getAttribute('aria-busy') === 'true' || confirm.hasAttribute('disabled');

      expect(busy).toBe(true);

    });

  });



  it('keyboard Enter opens manage billing confirmation', async () => {

    seedShellAuth('owner');

    const user = userEvent.setup();

    renderLevel11Shell('/app/settings/billing');

    await waitForBillingLoaded();

    const manage = screen.getByRole('button', { name: BILLING_COPY.manageBilling });

    manage.focus();

    await user.keyboard('{Enter}');

    expect(screen.getByText(BILLING_COPY.manageBillingConfirmTitle)).toBeInTheDocument();

  });



  it('double click does not duplicate portal attempts', async () => {

    seedShellAuth('owner');

    const user = userEvent.setup();

    renderLevel11Shell('/app/settings/billing');

    await waitForBillingLoaded();

    await user.click(screen.getByRole('button', { name: BILLING_COPY.manageBilling }));

    const confirm = await screen.findByRole('button', { name: BILLING_COPY.manageBillingConfirmAction });

    await user.click(confirm);

    await user.click(confirm);

    expect(getBillingPortalAttemptCount()).toBe(1);

  });



  it('network_error state renders safe recovery', async () => {

    setBillingTestMode('network_error');

    seedShellAuth('owner');

    renderLevel11Shell('/app/settings/billing');

    await waitForBillingState('network_error');

    expect(screen.getByText(BILLING_COPY.networkError)).toBeInTheDocument();

  });



  it('portal_unavailable state renders safe recovery', async () => {

    setBillingTestMode('portal_unavailable');

    seedShellAuth('owner');

    renderLevel11Shell('/app/settings/billing');

    await waitForBillingState('portal_unavailable');

    expect(screen.getByText(BILLING_COPY.portalUnavailable)).toBeInTheDocument();

  });

});



describe('Level 11 Harness — billing role matrix', () => {

  it('billing role matrix — owner can manage', async () => {

    seedShellAuth('owner');

    renderLevel11Shell('/app/settings/billing');

    await waitForBillingLoaded();

    expect(document.querySelector('[data-billing-manage-action]')).toBeTruthy();

  });



  it('billing role matrix — admin can manage', async () => {

    seedShellAuth('admin');

    renderLevel11Shell('/app/settings/billing');

    await waitForBillingLoaded();

    expect(document.querySelector('[data-billing-manage-action]')).toBeTruthy();

  });



  it('billing role matrix — billing_only can manage', async () => {

    seedShellAuth('billing_only');

    renderLevel11Shell('/app/settings/billing');

    await waitForBillingLoaded();

    expect(document.querySelector('[data-billing-manage-action]')).toBeTruthy();

  });



  it('billing role matrix — manager view without manage', async () => {

    seedShellAuth('manager');

    renderLevel11Shell('/app/settings/billing');

    await waitForBillingLoaded();

    expect(document.querySelector('[data-billing-manage-action]')).toBeNull();

    expect(document.querySelector('[data-billing-read-only]')).toBeTruthy();

  });



  it('billing role matrix — viewer read-only', async () => {

    seedShellAuth('viewer');

    renderLevel11Shell('/app/settings/billing');

    await waitForBillingLoaded();

    expect(document.querySelector('[data-billing-manage-action]')).toBeNull();

    expect(document.querySelector('[data-billing-read-only]')).toBeTruthy();

  });



  it('billing role matrix — unknown_role permission denied', async () => {

    seedShellAuth('unknown_role');

    renderLevel11Shell('/app/settings/billing');

    await waitForBillingState('permission_denied');

    expect(screen.getByText(BILLING_COPY.permissionDenied)).toBeInTheDocument();

  });

});



describe('Level 11 Harness — billing privacy and tenant boundary', () => {

  it('cross_tenant_billing fails closed', async () => {

    setBillingTestMode('cross_tenant_billing');

    seedShellAuth('owner');

    renderLevel11Shell('/app/settings/billing');

    await waitForBillingState('cross_tenant_denied');

  });



  it('payment method shows last4 only not full PAN', async () => {

    seedShellAuth('owner');

    renderLevel11Shell('/app/settings/billing');

    await waitForBillingLoaded();

    const text = document.querySelector('[data-billing-payment-method]')?.textContent ?? '';

    expect(text).toContain('4242');

    expect(text).not.toMatch(/\d{16}/);

  });

});



describe('Level 11 Harness — plan-gating absence matrix', () => {

  const routes = [

    { path: '/app', marker: '[data-command-center-loaded="true"]', label: 'Overview' },

    { path: '/app/claims/claim_0001', marker: '[data-claim-detail-loaded]', label: 'claims' },


    { path: '/app/audit', marker: '[data-audit-ledger-page]', label: 'audit' },

    { path: '/app/channels', marker: '[data-channels-page]', label: 'channels' },

  ] as const;



  it.each(routes)('plan gating absence — $label unchanged for viewer', async ({ path, marker }) => {

    seedShellAuth('viewer');

    renderLevel11Shell(path);

    await waitFor(() => expect(document.querySelector(marker)).toBeTruthy());

    expect(document.querySelector('[data-route-recovery-panel]')).toBeNull();

  });



  it('plan gating absence — channel executive actions remain for owner', async () => {
    seedShellAuth('owner');
    renderLevel11Shell('/app/channels?expand=ch_paid_search__google_ads');
    await waitFor(() => expect(document.querySelector('[data-channel-inline-expansion]')).toBeTruthy());
    expect(screen.getByRole('link', { name: /Review \d+ claims?/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Hold spend/i })).toBeInTheDocument();
  });

  it('trust operator surface remains reachable without channel TrustEnvelope expansion', async () => {
    seedShellAuth('owner');
    const { renderMountedTrustEnvelopeDrawer } = await import('./level8.helpers');
    renderMountedTrustEnvelopeDrawer('env_0001');
    await waitFor(() => expect(document.querySelector('[data-trust-envelope-operator-view]')).toBeTruthy());
    expect(screen.getByRole('button', { name: /Export report/i })).toBeInTheDocument();
  });
});



describe('Level 11 Harness — route recovery matrix', () => {

  it('unknown authenticated app route shows recovery panel', async () => {

    seedShellAuth('owner');

    renderLevel11Shell('/app/does-not-exist');

    await waitFor(() => expect(document.querySelector('[data-route-recovery-panel]')).toBeTruthy());

    expect(screen.getByText(ROUTE_RECOVERY_COPY.notFoundTitle)).toBeInTheDocument();

  });



  it('unknown settings route shows recovery panel', async () => {

    seedShellAuth('owner');

    renderLevel11Shell('/app/settings/unknown-section');

    await waitFor(() => expect(document.querySelector('[data-route-recovery-panel]')).toBeTruthy());

  });



  it('unknown public route uses public-safe recovery', async () => {

    renderPublicApp('/does-not-exist-public');

    await waitFor(() => expect(document.querySelector('[data-public-route-not-found]')).toBeTruthy());

    expect(screen.getByText(ROUTE_RECOVERY_COPY.returnToLogin)).toBeInTheDocument();

  });



  it('Return to Command Center resolves when tenant exists', async () => {

    seedShellAuth('owner');

    renderLevel11Shell('/app/unknown-nested');

    await waitFor(() => expect(document.querySelector('[data-route-recovery-command-center]')).toBeTruthy());

    expect(document.querySelector('[data-route-recovery-command-center]')?.getAttribute('href')).toBe('/app');

  });



  it('tenant-missing unknown route redirects to workspace creation', async () => {

    seedShellAuthWithoutTenant('owner');

    const { router } = renderLevel11Shell('/app/unknown-without-tenant');

    await waitFor(() => expect(router.state.location.pathname).toBe('/signup'));

    await waitFor(() => expect(document.querySelector('[data-create-organization-modal]')).toBeTruthy());

    expect(document.querySelector('[data-route-recovery-command-center]')).toBeNull();

  });



  it('restricted-role unknown route shows recovery panel', async () => {

    seedShellAuth('viewer');

    renderLevel11Shell('/app/unknown-restricted-role');

    await waitFor(() => expect(document.querySelector('[data-route-recovery-panel]')).toBeTruthy());

  });



  it('redirect-loop absence — Command Center does not return to unknown route', async () => {

    seedShellAuth('owner');

    const user = userEvent.setup();

    const { router } = renderLevel11Shell('/app/loop-check-unknown');

    await waitFor(() => expect(document.querySelector('[data-route-recovery-panel]')).toBeTruthy());

    const cc = document.querySelector('[data-route-recovery-command-center]') as HTMLElement;

    await user.click(cc);

    await waitFor(() => expect(router.state.location.pathname).toBe('/app'));

    expect(document.querySelector('[data-route-recovery-panel]')).toBeNull();

    expect(document.querySelector('[data-command-center-loaded="true"]')).toBeTruthy();

  });



  it('invalid dynamic object route uses domain not-found not generic recovery', async () => {

    seedShellAuth('owner');

    renderLevel11Shell('/app/claims/claim_does_not_exist');

    await waitFor(() => expect(document.querySelector('[data-claim-detail-page]')).toBeTruthy());

    await waitFor(() => expect(document.querySelector('[data-detail-state="not_found"]')).toBeTruthy());

    expect(document.querySelector('[data-route-recovery-panel]')).toBeNull();

  });

});



describe('Level 11 Harness — route graph preservation', () => {

  it.each(ROUTE_PRESERVATION_CASES)(

    'valid route $path is not swallowed by wildcard recovery',

    async ({ path, marker }) => {

      seedShellAuth('owner');

      renderLevel11Shell(path);

      if (path.includes('/settings/billing')) {

        await waitForBillingLoaded();

      } else {

        await waitFor(() => expect(document.querySelector(marker)).toBeTruthy());

      }

      expect(document.querySelector('[data-route-recovery-panel]')).toBeNull();

    },

  );

});



describe('Level 11 Harness — accessibility, responsive, boundedness', () => {

  it('375px billing page mounted check', async () => {

    setMobileViewport375();

    seedShellAuth('owner');

    renderLevel11Shell('/app/settings/billing');

    await waitForBillingLoaded();

    assertNoShellHorizontalScroll();

  });



  it('1280px billing page mounted check', async () => {

    setDesktopViewport1280();

    seedShellAuth('owner');

    renderLevel11Shell('/app/settings/billing');

    await waitForBillingLoaded();

    assertNoShellHorizontalScroll();

  });



  it('375px route recovery mounted check', async () => {

    setMobileViewport375();

    seedShellAuth('owner');

    renderLevel11Shell('/app/missing-mobile');

    await waitFor(() => expect(document.querySelector('[data-route-recovery-panel]')).toBeTruthy());

    assertNoShellHorizontalScroll();

  });



  it('1280px route recovery mounted check', async () => {

    setDesktopViewport1280();

    seedShellAuth('owner');

    renderLevel11Shell('/app/missing-desktop');

    await waitFor(() => expect(document.querySelector('[data-route-recovery-panel]')).toBeTruthy());

    assertNoShellHorizontalScroll();

  });



  it('keyboard focus — Return to Command Center reachable', async () => {

    seedShellAuth('owner');

    renderLevel11Shell('/app/missing-keyboard');

    await waitFor(() => expect(document.querySelector('[data-route-recovery-command-center]')).toBeTruthy());

    const link = document.querySelector('[data-route-recovery-command-center]') as HTMLElement;

    link.focus();

    expect(document.activeElement).toBe(link);

  });



  it('invoice table bounded scroll wrapper', async () => {

    seedShellAuth('owner');

    renderLevel11Shell('/app/settings/billing');

    await waitForBillingLoaded();

    assertInvoiceTableBounded();

  });



  it('billing error banner uses alert semantics', async () => {

    setBillingTestMode('network_error');

    seedShellAuth('owner');

    renderLevel11Shell('/app/settings/billing');

    await waitForBillingState('network_error');

    expect(document.querySelector('[role="alert"]')).toBeTruthy();

  });

});



describe('Level 11 Harness — sabotage', () => {

  it('source sabotage probes fire on clean tree', () => {

    const billingPage = readFileSync(

      join(process.cwd(), 'src/components/billing/BillingPage/BillingPage.tsx'),

      'utf8',

    );

    const recovery = readFileSync(join(process.cwd(), 'src/routeRecovery/RouteRecoveryPanel.tsx'), 'utf8');

    const publicNotFound = readFileSync(join(process.cwd(), 'src/routeRecovery/PublicRouteNotFoundPage.tsx'), 'utf8');

    const governance = readFileSync(join(process.cwd(), 'src/app/routes/GovernanceRoutes.tsx'), 'utf8');

    const sample = billingPage + recovery + publicNotFound + governance;

    const sabotage = runLevel11SabotageProbes(sample);

    const triggered = sabotage.filter((p) => p.triggered);

    expect(triggered.map((p) => p.name)).toEqual([]);

  });



  it('source sabotage probes detect missing billing route', () => {

    const bad = 'export function X() { return null; }';

    const triggered = runLevel11SabotageProbes(bad).filter((p) => p.triggered);

    expect(triggered.length).toBeGreaterThan(0);

  });



  it('runLevel11SourceSabotageProbes clean on harness file', () => {

    expect(runLevel11SourceSabotageProbes().every((p) => !p.triggered)).toBe(true);

  });

});

