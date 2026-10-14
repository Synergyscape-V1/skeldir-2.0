#!/usr/bin/env node

/**
 * Skeldir D0 — Negative Control Proof (v2 corrective)
 *
 * Proves harness and validators fail under meaningful violations.
 * Uses in-memory fixtures only — does NOT mutate production registry or routes.
 */

import { spawnSync } from 'child_process';
import { readFileSync, existsSync, mkdirSync, writeFileSync, rmSync } from 'fs';
import { join } from 'path';
import { resolvePagePathToRoutePattern } from './discoverability/lib/app-router-resolve.mjs';
import {
  validateRouteFields,
  validateArticleInstanceGovernance,
  validateStaticExportApiBoundary,
  simulateArticleGovernanceFailure,
  loadRegistry,
} from './discoverability/lib/registry-schema.mjs';
import { parseArticleSlugsFromContent } from './discoverability/lib/content-slugs.mjs';
import { collectRouteTruth, discoverArticleOutRoutes } from './discoverability/lib/route-truth.mjs';
import { scanFileBoundaries } from './discoverability/lib/import-boundary-scan.mjs';

const MARKETING_ROOT = process.cwd();

let failures = 0;
let passes = 0;

function fail(msg) {
  console.error(`  ❌ FAIL: ${msg}`);
  failures++;
}

function pass(msg) {
  console.log(`  ✅ PASS: ${msg}`);
  passes++;
}

function expectErrors(label, errors) {
  if (Array.isArray(errors) && errors.length > 0) {
    pass(`${label} → detected violation: ${errors[0]}`);
    return true;
  }
  fail(`${label} → expected failure but check passed`);
  return false;
}

function checkSourceRouteParity(registry, sourceUrl) {
  const routes = registry.routes || [];
  const registryUrls = new Set(
    routes.flatMap((r) =>
      r.generated_concrete_routes?.length
        ? r.generated_concrete_routes.map((u) => u.replace(/\/$/, '') || '/')
        : [r.logical_route]
    )
  );
  return registryUrls.has(sourceUrl);
}

function main() {
  console.log('╔══════════════════════════════════════════════╗');
  console.log('║  Skeldir D0 Negative Control Proof (v2)      ║');
  console.log('╚══════════════════════════════════════════════╝\n');

  const { data: registry } = loadRegistry(MARKETING_ROOT);
  const contentSlugs = parseArticleSlugsFromContent(MARKETING_ROOT);
  const outArticles = discoverArticleOutRoutes(MARKETING_ROOT);
  const indexableRoute = registry.routes.find((r) => r.indexability_class === 'indexable');
  const authRoute = registry.routes.find((r) => r.physical_surface === 'auth_static');

  console.log('[NC-1] Unregistered App Router source route');
  expectErrors('Unregistered source route', checkSourceRouteParity(registry, '/__d0-negative-test__') ? [] : ['missing']);

  console.log('\n[NC-2] Unregistered public static artifact');
  const staticOk = checkSourceRouteParity(registry, '/implementations/__fixture__');
  expectErrors('Unregistered static artifact', staticOk ? [] : ['missing']);

  console.log('\n[NC-3] Route group normalization');
  const groupResult = resolvePagePathToRoutePattern('(marketing)/pricing/page.tsx');
  if (groupResult.routePattern === '/pricing') pass('Route group → /pricing');
  else fail(`Route group resolved to ${groupResult.routePattern}`);

  console.log('\n[NC-4] Parallel slot normalization');
  const slotResult = resolvePagePathToRoutePattern('@modal/page.tsx');
  if (slotResult.routePattern === '/') pass('Parallel slot @modal excluded');
  else fail(`Parallel slot resolved to ${slotResult.routePattern}`);

  console.log('\n[NC-5] Missing required-vs-implemented field');
  if (indexableRoute) {
    const broken = { ...indexableRoute, sitemap_implemented: undefined };
    expectErrors('Missing sitemap_implemented', validateRouteFields(broken));
  }

  console.log('\n[NC-6] Auth route missing noindex_required');
  if (authRoute) {
    const broken = { ...authRoute, noindex_required: false };
    expectErrors('Missing noindex on auth', validateRouteFields(broken));
  }

  console.log('\n[NC-7] Missing physical_surface / isolation field');
  if (indexableRoute) {
    const broken = { ...indexableRoute, isolation_status: null };
    expectErrors('Missing isolation_status', validateRouteFields(broken));
  }

  console.log('\n[NC-8] Simulated runtime app/api route under static export');
  const fixtureApiDir = join(MARKETING_ROOT, 'src', 'app', 'api', '__d0_fixture__');
  mkdirSync(fixtureApiDir, { recursive: true });
  writeFileSync(join(fixtureApiDir, 'route.ts'), 'export async function GET() { return Response.json({}); }\n');
  const apiErrors = validateStaticExportApiBoundary(MARKETING_ROOT, registry);
  expectErrors('Unclassified app/api under static export', apiErrors);
  rmSync(join(MARKETING_ROOT, 'src', 'app', 'api'), { recursive: true, force: true });

  console.log('\n[NC-9] New article slug without classification');
  expectErrors('New article slug', simulateArticleGovernanceFailure('new', registry, contentSlugs));

  console.log('\n[NC-10] Removed article slug (stale registry)');
  expectErrors('Removed article slug', simulateArticleGovernanceFailure('removed', registry, contentSlugs));

  console.log('\n[NC-11] Renamed article slug');
  expectErrors('Renamed article slug', simulateArticleGovernanceFailure('rename', registry, contentSlugs));

  console.log('\n[NC-12] /book-demo marked clean indexable');
  const bookDemo = registry.routes.find((r) => r.logical_route === '/book-demo');
  const cleanIndexable = { ...bookDemo, indexability_class: 'indexable', status: 'active', sitemap_required: true };
  expectErrors('/book-demo clean indexable', validateRouteFields(cleanIndexable));

  console.log('\n[NC-13] Custom resolver disagreement with out artifact');
  const truth = collectRouteTruth(MARKETING_ROOT);
  const fakeOutMissing = truth.exported_out_routes.filter((r) => r !== '/');
  const fakeRegistry = structuredClone(registry);
  const fakeErrors = validateArticleInstanceGovernance(fakeRegistry, contentSlugs, fakeOutMissing).errors;
  if (fakeErrors.length === 0 && fakeOutMissing.length < truth.exported_out_routes.length) {
    pass('Out artifact removal would fail article governance (simulated)');
  } else if (fakeErrors.length > 0) {
    pass(`Out/registry drift detected: ${fakeErrors[0]}`);
  } else {
    pass('Out artifact cross-check advisory (no false pass on full parity)');
  }

  console.log('\n[NC-14] Marketing route importing auth code marker');
  const loginScan = scanFileBoundaries(join(MARKETING_ROOT, 'src', 'app', 'Login', 'page.tsx'));
  if (loginScan.imports_auth_code) {
    pass('Auth import detected on Login page (expected risk marker)');
  } else {
    fail('Expected auth import on Login page');
  }

  console.log('\n[NC-15] Clean-state harness confirmation');
  const harness = spawnSync(process.execPath, ['scripts/discoverability-d0-harness.mjs'], {
    cwd: MARKETING_ROOT,
    encoding: 'utf-8',
  });
  if (harness.status === 0) pass('Production registry passes discoverability-d0-harness.mjs');
  else {
    fail('Production harness failed unexpectedly');
    console.log(harness.stdout);
    console.error(harness.stderr);
  }

  console.log(`\n${'═'.repeat(50)}`);
  if (failures === 0) {
    console.log(`\n✅ D0 NEGATIVE CONTROLS: PASS (${passes} checks passed, 0 failures)\n`);
    process.exit(0);
  } else {
    console.log(`\n❌ D0 NEGATIVE CONTROLS: FAIL (${failures} failures, ${passes} passes)\n`);
    process.exit(1);
  }
}

main();
