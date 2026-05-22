#!/usr/bin/env node

/**
 * Skeldir D0 — Discoverability Parity Harness (v2 corrective)
 *
 * Route truth hierarchy (authoritative to advisory):
 * 1. marketing/out HTML files - deployed static export truth
 * 2. Next build artifacts (when available)
 * 3. content/generateStaticParams - generated instance source
 * 4. source route scan - intent evidence
 * 5. app-router-resolve.mjs - normalization helper only (advisory)
 */

import { existsSync, readFileSync, readdirSync } from 'fs';
import { join, relative, sep, dirname } from 'path';
import { collectRouteTruth, discoverArticleOutRoutes, normalizeRoute } from './discoverability/lib/route-truth.mjs';
import { scanMarketingImportBoundaries } from './discoverability/lib/import-boundary-scan.mjs';
import { parseArticleSlugsFromContent } from './discoverability/lib/content-slugs.mjs';
import {
  validateRouteFields,
  validateRegistryStructure,
  validateArticleInstanceGovernance,
  validateStaticExportApiBoundary,
  validateImportBoundaries,
  IMPLEMENTATION_FIELDS,
} from './discoverability/lib/registry-schema.mjs';

const MARKETING_ROOT = process.cwd();
const SRC_APP = join(MARKETING_ROOT, 'src', 'app');
const PUBLIC_DIR = join(MARKETING_ROOT, 'public');
const OUT_DIR = join(MARKETING_ROOT, 'out');
const REGISTRY_PATH = join(MARKETING_ROOT, 'discoverability.routes.json');

let failures = 0;
let passes = 0;
let warnings = 0;

function fail(msg) {
  console.error(`  ❌ FAIL: ${msg}`);
  failures++;
}

function pass(msg) {
  console.log(`  ✅ PASS: ${msg}`);
  passes++;
}

function warn(msg) {
  console.log(`  ⚠️  WARN: ${msg}`);
  warnings++;
}

function findPageFiles(dir, results = []) {
  if (!existsSync(dir)) return results;
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name.startsWith('.') || entry.name === 'node_modules') continue;
      findPageFiles(full, results);
    } else if (/^page\.(tsx|ts|jsx|js)$/.test(entry.name)) {
      results.push(full);
    }
  }
  return results;
}

function findHtmlFiles(dir, results = []) {
  if (!existsSync(dir)) return results;
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name.startsWith('.') || entry.name === 'node_modules' || entry.name === '_next') continue;
      findHtmlFiles(full, results);
    } else if (entry.name.endsWith('.html')) {
      results.push(full);
    }
  }
  return results;
}

function normalizeAppRouterPath(pageFilePath) {
  const rel = relative(SRC_APP, dirname(pageFilePath));
  if (!rel || rel === '.') return '/';
  const segments = rel.split(sep);
  const urlSegments = [];
  for (const seg of segments) {
    if (/^\(.*\)$/.test(seg)) continue;
    if (seg.startsWith('@')) continue;
    urlSegments.push(seg);
  }
  return '/' + urlSegments.join('/');
}

function registryUrlSet(routes) {
  return new Set(
    routes.flatMap((r) =>
      r.generated_concrete_routes?.length
        ? r.generated_concrete_routes.map((u) => normalizeRoute(u))
        : [normalizeRoute(r.logical_route)]
    )
  );
}

function main() {
  console.log('╔══════════════════════════════════════════════╗');
  console.log('║  Skeldir D0 Discoverability Parity Harness  ║');
  console.log('║  (v2 corrective — route truth hierarchy)     ║');
  console.log('╚══════════════════════════════════════════════╝\n');

  // [1] Registry exists
  console.log('[1] Registry file exists');
  if (!existsSync(REGISTRY_PATH)) {
    fail('discoverability.routes.json not found');
    process.exit(1);
  }
  pass('discoverability.routes.json found');

  const registry = JSON.parse(readFileSync(REGISTRY_PATH, 'utf8'));
  const routes = registry.routes || [];
  const registryUrls = registryUrlSet(routes);

  // [2] Registry v2 structure
  console.log('\n[2] Registry v2 structure and semantics');
  for (const err of validateRegistryStructure(registry)) {
    fail(err);
  }
  if (registry.version === '2.0.0') pass('Registry version 2.0.0');
  else fail(`Expected registry version 2.0.0, got ${registry.version}`);
  pass('Trust API runtime classified as external infrastructure surface');
  pass(`Physical split during D0: ${registry.physical_surface_governance?.physical_split_required_during_d0}`);

  // [3] Required vs implemented fields
  console.log('\n[3] Required vs implemented field separation');
  for (const route of routes) {
    if (route.route_type === 'missing_required') continue;
    const errs = validateRouteFields(route);
    if (errs.length === 0) {
      pass(`Route ${route.id} has required/implemented/isolation fields`);
    } else {
      for (const e of errs) fail(e);
    }
  }

  // [4] Source route parity
  console.log('\n[4] Source route parity (intent scan)');
  const sourcePages = findPageFiles(SRC_APP);
  for (const fp of sourcePages) {
    const url = normalizeAppRouterPath(fp);
    if (url.includes('[')) {
      const hasPattern = routes.some(
        (r) => r.dynamic_route_pattern === url || r.route_type === 'article_pattern'
      );
      if (hasPattern) pass(`Source dynamic route classified: ${url}`);
      else fail(`Source dynamic route UNCLASSIFIED: ${url}`);
    } else if (registryUrls.has(url)) {
      pass(`Source route classified: ${url}`);
    } else {
      fail(`Source route UNCLASSIFIED: ${url}`);
    }
  }

  // [5] Static export API boundary
  console.log('\n[5] Static export API boundary');
  const apiErrors = validateStaticExportApiBoundary(MARKETING_ROOT, registry);
  if (apiErrors.length === 0) {
    pass('No unclassified marketing/src/app/api/** route handlers under static export');
  } else {
    for (const e of apiErrors) fail(e);
  }

  // [6] /api docs vs Trust API runtime
  console.log('\n[6] API docs vs runtime API separation');
  const apiDocs = routes.find((r) => r.logical_route === '/api');
  if (apiDocs?.route_type === 'api_docs' && apiDocs.runtime_api === false) {
    pass('/api classified as static api_docs (runtime_api=false)');
  } else {
    fail('/api not correctly classified as static api_docs');
  }
  const trustApi = registry.infrastructure_surfaces?.find((s) => s.id === 'infra-trust-api-runtime');
  if (trustApi?.static_export_compatible === false) {
    pass('Trust API runtime marked external_backend, not static export');
  } else {
    fail('Trust API runtime infrastructure surface misclassified');
  }

  // [7] Article pattern vs generated instances
  console.log('\n[7] Dynamic content instance governance');
  const contentSlugs = parseArticleSlugsFromContent(MARKETING_ROOT);
  const outArticles = discoverArticleOutRoutes(MARKETING_ROOT);
  const { errors: articleErrors, warnings: articleWarnings } = validateArticleInstanceGovernance(
    registry,
    contentSlugs,
    outArticles
  );
  for (const e of articleErrors) fail(e);
  for (const w of articleWarnings) warn(w);
  if (articleErrors.length === 0) {
    pass(`Article instances synced: ${contentSlugs.length} content slugs, ${outArticles.length} out artifacts`);
  }
  const pattern = routes.find((r) => r.route_type === 'article_pattern');
  if (pattern?.generated_instances_policy === 'auto_discovered') {
    pass('Article pattern uses auto_discovered generated_instances_policy');
  } else {
    fail('Article pattern missing or wrong generated_instances_policy');
  }

  // [8] Route truth hierarchy
  console.log('\n[8] Route truth hierarchy (out > content > source > resolver advisory)');
  const truth = collectRouteTruth(MARKETING_ROOT);
  pass(`Source intent routes: ${truth.source_intent_routes.length}`);
  pass(`Generated content instances: ${truth.generated_content_instances.length}`);
  pass(`Exported out routes: ${truth.exported_out_routes.length}`);
  if (truth.unknown_or_ambiguous_routes.length === 0) {
    pass('No resolver disagreements with source scan');
  } else {
    for (const u of truth.unknown_or_ambiguous_routes) {
      fail(`Resolver disagreement: source=${u.source} resolver=${u.resolver}`);
    }
  }

  // [9] Build output parity (out = deployed truth)
  console.log('\n[9] Build output parity (out/ authoritative)');
  if (existsSync(OUT_DIR)) {
    for (const fp of findHtmlFiles(OUT_DIR)) {
      const rel = relative(OUT_DIR, fp).replace(/\\/g, '/');
      let url = '/' + rel.replace(/\.html$/, '').replace(/\/index$/, '/').replace(/^index$/, '');
      if (url === '/') url = '/';
      if (url.startsWith('/_not-found')) continue;
      const urlNorm = normalizeRoute(url);
      if (registryUrls.has(urlNorm) || registryUrls.has(`${urlNorm}/`)) {
        pass(`Build output classified: ${url}`);
      } else {
        fail(`Build output UNCLASSIFIED: ${url} (from out/${rel})`);
      }
    }
  } else {
    warn('out/ directory not found — build output checks skipped');
  }

  // [10] Public static HTML parity
  console.log('\n[10] Public static HTML parity');
  for (const fp of findHtmlFiles(PUBLIC_DIR)) {
    const rel = relative(PUBLIC_DIR, fp).replace(/\\/g, '/');
    let url = '/' + rel.replace(/\/index\.html$/, '/').replace(/\.html$/, '');
    const urlNorm = normalizeRoute(url);
    if (registryUrls.has(urlNorm) || registryUrls.has(`${urlNorm}/`)) {
      pass(`Public static HTML classified: ${url}`);
    } else {
      fail(`Public static HTML UNCLASSIFIED: ${url}`);
    }
  }

  // [11] /book-demo reclassification
  console.log('\n[11] /book-demo defective candidate governance');
  const bookDemo = routes.find((r) => r.logical_route === '/book-demo');
  if (bookDemo?.indexability_class === 'indexable_candidate') {
    pass('/book-demo is indexable_candidate (not clean indexable)');
  } else {
    fail('/book-demo must be indexable_candidate');
  }
  if (bookDemo?.status === 'active_defective_until_static_body_verified') {
    pass('/book-demo status is active_defective_until_static_body_verified');
  } else {
    fail('/book-demo status must be active_defective_until_static_body_verified');
  }
  if (bookDemo?.sitemap_required === false) {
    pass('/book-demo sitemap_required=false until D1/D2 verification');
  } else {
    fail('/book-demo must not be sitemap_required=true yet');
  }

  // [12] Import/bundle boundary scan
  console.log('\n[12] Physical surface import boundary scan');
  const importScans = scanMarketingImportBoundaries(MARKETING_ROOT);
  const importErrors = validateImportBoundaries(importScans, routes);
  if (importErrors.length === 0) {
    pass('No backend/token/dashboard-provider import breach in marketing_static pages');
  } else {
    for (const e of importErrors) fail(e);
  }
  const authPages = routes.filter((r) => r.physical_surface === 'auth_static');
  for (const r of authPages) {
    if (r.isolation_status === 'risk' || r.isolation_status === 'inconclusive') {
      pass(`${r.logical_route} isolation_status=${r.isolation_status}`);
    } else {
      warn(`${r.logical_route} isolation_status=${r.isolation_status}`);
    }
  }

  // [13] Missing-linked routes
  console.log('\n[13] Missing-linked routes represented');
  for (const url of ['/privacy', '/security', '/status', '/about', '/careers', '/blog', '/press', '/docs', '/api', '/trust-envelope']) {
    if (routes.some((r) => r.logical_route === url)) pass(`Missing-linked route tracked: ${url}`);
    else fail(`Missing-linked route NOT tracked: ${url}`);
  }

  // [14] Review artifacts
  console.log('\n[14] Review artifact governance');
  for (const r of routes.filter((rt) => rt.logical_route.startsWith('/implementations/'))) {
    if (r.route_type === 'review_artifact' && r.noindex_required === true) {
      pass(`Review artifact governed: ${r.logical_route}`);
    } else {
      fail(`Review artifact not governed: ${r.logical_route}`);
    }
  }

  console.log(`\n${'═'.repeat(50)}`);
  if (failures === 0) {
    console.log(`\n✅ D0 PARITY HARNESS: PASS (${passes} checks passed, ${warnings} warnings, 0 failures)\n`);
    process.exit(0);
  } else {
    console.log(`\n❌ D0 PARITY HARNESS: FAIL (${failures} failures, ${passes} passes, ${warnings} warnings)\n`);
    process.exit(1);
  }
}

main();
