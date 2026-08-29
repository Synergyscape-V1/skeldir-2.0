import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { canManageBilling, canViewBilling } from '../billing/permissions';
import { getBillingPortalAttemptCount, resetBillingTestState } from '../billing/billingClient';
import { LEVEL11_PERMITTED_ROUTES } from '../auth/redirectGuard';

const ROOT = join(import.meta.dirname, '..', '..');

const SCAN_DIRS = [
  join(ROOT, 'src', 'billing'),
  join(ROOT, 'src', 'routeRecovery'),
  join(ROOT, 'src', 'components', 'billing'),
  join(ROOT, 'src', 'app', 'routes', 'ShellRoutes.tsx'),
  join(ROOT, 'src', 'app', 'routes', 'GovernanceRoutes.tsx'),
  join(ROOT, 'src', 'app', 'App.tsx'),
  join(ROOT, 'evidence', 'Level_11'),
];

const FORBIDDEN_TRUST_SEMANTICS = [
  'AuthorityBadge',
  'verified revenue truth',
  'creates verified revenue',
  'TrustEnvelope integrity',
  'auto-optimize',
  'guaranteed lift',
  'plan gating hides',
];

const FORBIDDEN_SENSITIVE = [
  '4242424242424242',
  'sk_live_',
  'pk_live_',
  'whsec_',
  'card_number',
  'full_pan',
];

const REQUIRED_L11_MARKERS = [
  'BillingPage',
  'BillingSettingsRoute',
  'path="settings/billing"',
  'data-billing-page',
  'data-billing-trust-boundary',
  'data-route-recovery-panel',
  'data-public-route-not-found',
  'data-settings-billing-link',
  'RouteRecoveryPanel',
  'PublicRouteNotFoundPage',
  'canManageBilling',
  'canViewBilling',
];

function walk(target: string, acc: string[] = []): string[] {
  if (!statSync(target).isDirectory()) {
    acc.push(target);
    return acc;
  }
  for (const entry of readdirSync(target)) {
    const full = join(target, entry);
    if (statSync(full).isDirectory()) walk(full, acc);
    else if (/\.(tsx|ts|md|json|css)$/.test(entry)) acc.push(full);
  }
  return acc;
}

export function runLevel11NegativeScopeScan() {
  const files = SCAN_DIRS.flatMap((dir) => {
    try {
      return walk(dir, []);
    } catch {
      return [];
    }
  });
  const violations: Array<{ file: string; type: string; value: string }> = [];

  for (const file of files) {
    const rel = relative(ROOT, file);
    if (rel.includes('.test.')) continue;
    const content = readFileSync(file, 'utf8');

    if (/\.(tsx|ts)$/.test(file) && (rel.includes('billing') || rel.includes('routeRecovery'))) {
      for (const term of FORBIDDEN_TRUST_SEMANTICS) {
        if (content.includes(term)) {
          violations.push({ file: rel, type: 'trust-semantics-corruption', value: term });
        }
      }
      for (const term of FORBIDDEN_SENSITIVE) {
        if (content.includes(term)) {
          violations.push({ file: rel, type: 'sensitive-billing-leak', value: term });
        }
      }
    }
  }

  return { filesScanned: files.length, violations };
}

export function assertLevel11ComponentsExist() {
  const paths = [
    join(ROOT, 'src', 'components', 'billing', 'BillingPage', 'BillingPage.tsx'),
    join(ROOT, 'src', 'routeRecovery', 'RouteRecoveryPanel.tsx'),
    join(ROOT, 'src', 'routeRecovery', 'PublicRouteNotFoundPage.tsx'),
    join(ROOT, 'src', 'app', 'routes', 'ShellRoutes.tsx'),
    join(ROOT, 'src', 'app', 'routes', 'GovernanceRoutes.tsx'),
    join(ROOT, 'src', 'app', 'App.tsx'),
    join(ROOT, 'src', 'billing', 'billingClient.ts'),
    join(ROOT, 'src', 'billing', 'permissions.ts'),
  ];
  const combined = paths.map((p) => readFileSync(p, 'utf8')).join('\n');
  const missing = REQUIRED_L11_MARKERS.filter((m) => !combined.includes(m));
  return { ok: missing.length === 0, missing };
}

export function runLevel11IntegrityProbes() {
  resetBillingTestState();
  return [
    { name: 'billing-view-owner', ok: canViewBilling('owner') },
    { name: 'billing-view-viewer', ok: canViewBilling('viewer') },
    { name: 'billing-manage-owner', ok: canManageBilling('owner') },
    { name: 'billing-manage-viewer-denied', ok: !canManageBilling('viewer') },
    { name: 'billing-manage-billing-only', ok: canManageBilling('billing_only') },
    { name: 'level11-permitted-route', ok: LEVEL11_PERMITTED_ROUTES.includes('/settings/billing') },
    { name: 'portal-attempt-counter', ok: getBillingPortalAttemptCount() === 0 },
  ];
}

export function runLevel11SabotageProbes(sourceSample: string) {
  return [
    { name: 'missing-billing-page', triggered: !sourceSample.includes('data-billing-page') },
    { name: 'missing-trust-boundary', triggered: !sourceSample.includes('data-billing-trust-boundary') },
    { name: 'authority-badge-on-billing', triggered: sourceSample.includes('AuthorityBadge') && sourceSample.includes('BillingPage') },
    { name: 'raw-card-in-billing', triggered: /\d{16}/.test(sourceSample) && sourceSample.includes('BillingPage') },
    { name: 'missing-route-recovery', triggered: !sourceSample.includes('data-route-recovery-panel') },
    { name: 'missing-public-not-found', triggered: !sourceSample.includes('data-public-route-not-found') },
    { name: 'missing-billing-nav-link', triggered: !sourceSample.includes('data-settings-billing-link') },
    { name: 'viewer-can-manage-without-check', triggered: /canManageBilling\('viewer'\)/.test(sourceSample) },
  ];
}

export function runLevel11SourceSabotageProbes() {
  const harness =
    readFileSync(join(ROOT, 'src', 'test', 'level11.harness.test.tsx'), 'utf8') +
    readFileSync(join(ROOT, 'src', 'test', 'level11.helpers.tsx'), 'utf8');
  return [
    { name: 'missing-billing-mounted', triggered: !harness.includes('/app/settings/billing') },
    { name: 'missing-role-matrix', triggered: !harness.includes('billing role matrix') },
    { name: 'missing-route-recovery-matrix', triggered: !harness.includes('route recovery matrix') },
    { name: 'missing-plan-gating-absence', triggered: !harness.includes('plan gating absence') },
    { name: 'missing-double-click', triggered: !harness.includes('double click') },
    { name: 'missing-cross-tenant', triggered: !harness.includes('cross_tenant_billing') },
    { name: 'missing-navigation-consistency', triggered: !harness.includes('Settings subnav') },
    { name: 'missing-375px', triggered: !harness.includes('375px') },
    { name: 'missing-1280px', triggered: !harness.includes('1280px') },
    { name: 'missing-source-sabotage-call', triggered: !harness.includes('runLevel11SourceSabotageProbes') },
    { name: 'missing-level10-regression', triggered: !harness.includes('runLevel10NegativeScopeScan') },
    { name: 'missing-permission-denied-mounted', triggered: !harness.includes('permission_denied state mounted') },
    { name: 'missing-loading-mounted', triggered: !harness.includes('loading state mounted') },
    { name: 'missing-empty-mounted', triggered: !harness.includes('empty invoice/payment state mounted') },
    { name: 'missing-confirmation-modal', triggered: !harness.includes('confirmation modal opens') },
    { name: 'missing-external-portal-hint', triggered: !harness.includes('external portal hint copy mounted') },
    { name: 'missing-aria-busy', triggered: !harness.includes('pending aria-busy') },
    { name: 'missing-keyboard-manage', triggered: !harness.includes('keyboard Enter opens manage billing') },
    { name: 'missing-settings-billing-nav', triggered: !harness.includes('billing reachable from Settings subnav') },
    { name: 'missing-session-guard', triggered: !harness.includes('missing session billing route redirects') },
    { name: 'missing-admin-role', triggered: !harness.includes('admin can manage') },
    { name: 'missing-manager-role', triggered: !harness.includes('manager view without manage') },
    { name: 'missing-unknown-role', triggered: !harness.includes('unknown_role permission denied') },
    { name: 'missing-trust-route-preservation', triggered: !harness.includes('[data-trust-envelope-operator-view]') && !harness.includes('[data-claim-trust-envelope-drawer]') },
    { name: 'missing-channel-route-preservation', triggered: !harness.includes('[data-channel-inline-expansion]') },
    { name: 'missing-budget-route-preservation', triggered: !harness.includes('[data-budget-detail-loaded]') },
    { name: 'missing-audit-route-preservation', triggered: !harness.includes('[data-audit-ledger-page]') },
    { name: 'missing-restricted-recovery', triggered: !harness.includes('restricted-role unknown route') },
    { name: 'missing-redirect-loop', triggered: !harness.includes('redirect-loop absence') },
    { name: 'missing-invalid-dynamic', triggered: !harness.includes('invalid dynamic object route') },
    { name: 'missing-invoice-bounded', triggered: !harness.includes('invoice table bounded') },
    { name: 'missing-visual-artifacts', triggered: !harness.includes('visual artifact index and PNG files') },
  ];
}

export function runLevel11SourceIntegrityProbes() {
  const harness =
    readFileSync(join(ROOT, 'src', 'test', 'level11.harness.test.tsx'), 'utf8') +
    readFileSync(join(ROOT, 'src', 'test', 'level11.helpers.tsx'), 'utf8');
  const base = runLevel11IntegrityProbes();
  return [
    ...base,
    { name: 'harness-billing-mounted', ok: harness.includes('/app/settings/billing') },
    { name: 'harness-role-matrix', ok: harness.includes('billing role matrix') },
    { name: 'harness-route-recovery', ok: harness.includes('route recovery matrix') },
    { name: 'harness-plan-gating-absence', ok: harness.includes('plan gating absence') },
    { name: 'harness-double-click', ok: harness.includes('double click') },
    { name: 'harness-cross-tenant', ok: harness.includes('cross_tenant_billing') },
    { name: 'harness-navigation', ok: harness.includes('Settings subnav') },
    { name: 'harness-375px', ok: harness.includes('375px') },
    { name: 'harness-1280px', ok: harness.includes('1280px') },
    { name: 'harness-source-sabotage', ok: harness.includes('runLevel11SourceSabotageProbes') },
    { name: 'harness-level10-regression', ok: harness.includes('runLevel10NegativeScopeScan') },
    { name: 'harness-viewer-read-only', ok: harness.includes('viewer read-only') },
    { name: 'harness-valid-dynamic-route', ok: harness.includes('invalid dynamic object route') },
    { name: 'harness-permission-denied', ok: harness.includes('permission_denied state mounted') },
    { name: 'harness-loading', ok: harness.includes('loading state mounted') },
    { name: 'harness-empty', ok: harness.includes('empty invoice/payment state mounted') },
    { name: 'harness-confirmation-modal', ok: harness.includes('confirmation modal opens') },
    { name: 'harness-external-portal', ok: harness.includes('external portal hint copy mounted') },
    { name: 'harness-aria-busy', ok: harness.includes('pending aria-busy') },
    { name: 'harness-keyboard-manage', ok: harness.includes('keyboard Enter opens manage billing') },
    { name: 'harness-settings-billing-nav', ok: harness.includes('billing reachable from Settings subnav') },
    { name: 'harness-session-guard', ok: harness.includes('missing session billing route redirects') },
    { name: 'harness-admin-role', ok: harness.includes('admin can manage') },
    { name: 'harness-manager-role', ok: harness.includes('manager view without manage') },
    { name: 'harness-unknown-role', ok: harness.includes('unknown_role permission denied') },
    { name: 'harness-trust-preservation', ok: harness.includes('[data-trust-envelope-operator-view]') || harness.includes('[data-claim-trust-envelope-drawer]') },
    { name: 'harness-channel-preservation', ok: harness.includes('[data-channel-inline-expansion]') },
    { name: 'harness-budget-preservation', ok: harness.includes('[data-budget-detail-loaded]') },
    { name: 'harness-audit-preservation', ok: harness.includes('[data-audit-ledger-page]') },
    { name: 'harness-restricted-recovery', ok: harness.includes('restricted-role unknown route') },
    { name: 'harness-redirect-loop', ok: harness.includes('redirect-loop absence') },
    { name: 'harness-invoice-bounded', ok: harness.includes('invoice table bounded') },
    { name: 'harness-visual-artifacts', ok: harness.includes('visual artifact index and PNG files') },
  ];
}

export function runLevel11NegativeScopeScanCli() {
  const scan = runLevel11NegativeScopeScan();
  const components = assertLevel11ComponentsExist();
  const probes = runLevel11IntegrityProbes();
  if (scan.violations.length > 0) {
    console.error('Level 11 scope violations:', scan.violations);
    process.exit(1);
  }
  if (!components.ok) {
    console.error('Missing Level 11 markers:', components.missing);
    process.exit(1);
  }
  const failedProbe = probes.find((p) => !p.ok);
  if (failedProbe) {
    console.error('Level 11 integrity probe failed:', failedProbe.name);
    process.exit(1);
  }
  console.log(`Level 11 scope scan: ${scan.filesScanned} files, 0 violations`);
  console.log(`Level 11 markers: ${REQUIRED_L11_MARKERS.length - components.missing.length}/${REQUIRED_L11_MARKERS.length}`);
  console.log(`Level 11 integrity probes: ${probes.filter((p) => p.ok).length}/${probes.length}`);
}

if (import.meta.url === `file://${process.argv[1]?.replace(/\\/g, '/')}`) {
  runLevel11NegativeScopeScanCli();
}
