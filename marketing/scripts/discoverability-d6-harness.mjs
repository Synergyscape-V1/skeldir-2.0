#!/usr/bin/env node

/**
 * Skeldir D6 — Evidence library architecture harness.
 */

import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { assertDiscoverabilityGitBranchPolicy } from './discoverability/lib/d2-crawl-graph.mjs';
import { readBuiltHtml } from './discoverability/lib/d5-trust-proof.mjs';
import {
  D6_CORE_EVIDENCE_ROUTES,
  D6_REQUIRED_MATRIX_QUERIES,
  computeEvidenceAllPairsSimilarity,
  loadBuyerQueryMatrix,
  loadEvidenceLibraryRegistry,
  validateBuyerQueryMatrixShape,
  validateD6EvidenceDetailHtml,
  validateD6EvidenceHubHtml,
  validateEvidenceLibraryRegistryShape,
} from './discoverability/lib/d6-evidence-library.mjs';
import { validateD6EvidenceFrontLoad } from './discoverability/lib/d6-evidence-frontload.mjs';
import {
  loadEntitySemanticsRegistry,
  validateD6EntitySemanticsDrift,
  validateEntitySemanticsRegistryShape,
} from './discoverability/lib/d6-entity-semantics.mjs';
import { validateD6MethodologyExposure } from './discoverability/lib/d6-methodology-exposure.mjs';
import { validateD6TrustEnvelopeExposure } from './discoverability/lib/d6-trust-envelope-exposure.mjs';
import { validateD6RevenueVerificationExposure } from './discoverability/lib/d6-revenue-verification-exposure.mjs';
import { validateD6AttributionMethodologyExposure } from './discoverability/lib/d6-attribution-methodology-exposure.mjs';
import { validateD6DiscrepancyTaxonomyExposure } from './discoverability/lib/d6-discrepancy-taxonomy-exposure.mjs';
import { validateD6AiBoundaryExposure } from './discoverability/lib/d6-ai-boundary-exposure.mjs';
import { validateD6SecurityExposure } from './discoverability/lib/d6-security-exposure.mjs';
import {
  loadStatusRegistry,
  validateD6StatusExposure,
} from './discoverability/lib/d6-status-exposure.mjs';
import {
  loadPressRegistry,
  loadPublicContactsRegistry,
  validateD6PressExposure,
} from './discoverability/lib/d6-press-exposure.mjs';
import {
  loadCareersRegistry,
  loadPublicContactsForCareers,
  validateD6CareersExposure,
} from './discoverability/lib/d6-careers-exposure.mjs';
import {
  loadApiSurfaceRegistry,
  loadPublicContactsForApi,
  validateD6ApiExposure,
} from './discoverability/lib/d6-api-exposure.mjs';
import {
  loadPrivacySurfaceRegistry,
  loadPublicContactsForPrivacy,
  validateD6PrivacyExposure,
} from './discoverability/lib/d6-privacy-exposure.mjs';
import {
  loadAboutSurfaceRegistry,
  validateD6AboutExposure,
} from './discoverability/lib/d6-about-exposure.mjs';

const MARKETING_ROOT = process.cwd();
let failures = 0;
let passes = 0;

/** @type {object[]} */
const frontLoadReportRows = [];
/** @type {object[]} */
const entitySemanticsReportRows = [];
/** @type {object[]} */
const similarityReportRows = [];

function fail(msg) {
  console.error(`  ❌ FAIL: ${msg}`);
  failures++;
}
function pass(msg) {
  console.log(`  ✅ PASS: ${msg}`);
  passes++;
}

function ensureBuild() {
  const skip =
    process.env.MARKETING_D6_SKIP_BUILD === '1' || process.argv.includes('--skip-build');
  if (skip) {
    const idx = path.join(MARKETING_ROOT, 'out', 'index.html');
    if (!fs.existsSync(idx)) {
      fail('MARKETING_D6_SKIP_BUILD=1 but out/index.html missing — run npm run build first');
      process.exit(1);
    }
    pass('npm run build skipped; using existing out/');
    return;
  }
  const b = spawnSync('npm run build', { cwd: MARKETING_ROOT, shell: true, stdio: 'inherit' });
  if (b.status !== 0) {
    fail('npm run build exited non-zero');
    process.exit(1);
  }
  pass('npm run build completed');
}

function gate(name) {
  console.log(`\n[${name}]`);
}

function printFrontLoadTable() {
  console.log('\n  Front-load placement (retrieval sections, normalized position in <main>):');
  console.log('  Route | Section | % in main | Result');
  const byRoute = new Map();
  for (const r of frontLoadReportRows) {
    if (!['Bottom line', 'Key Facts', 'Claims and evidence'].includes(r.section)) continue;
    if (!byRoute.has(r.route)) byRoute.set(r.route, []);
    byRoute.get(r.route).push(r);
  }
  for (const [route, rows] of byRoute) {
    const slug = route.replace('/resources/evidence/', '') || 'hub';
    const parts = rows.map(
      (r) => `${r.section.split(' ')[0]}=${(r.normalizedPositionInMain * 100).toFixed(1)}%`,
    );
    const ok = rows.every((r) => r.result === 'pass');
    console.log(`  ${slug} | ${parts.join(' | ')} | ${ok ? 'PASS' : 'FAIL'}`);
  }
}

function main() {
  console.log('╔══════════════════════════════════════════════════════════╗');
  console.log('║  Skeldir D6 — Evidence library architecture               ║');
  console.log('╚══════════════════════════════════════════════════════════╝\n');

  gate('0] Git branch policy');
  const gitErrs = assertDiscoverabilityGitBranchPolicy(MARKETING_ROOT);
  if (gitErrs.length) gitErrs.forEach(fail);
  else pass('Git branch policy satisfied (or skipped)');

  gate('1] Production build');
  ensureBuild();

  gate('2] Buyer query matrix files');
  const md = path.join(MARKETING_ROOT, 'BUYER_QUERY_CONTENT_MATRIX.md');
  if (!fs.existsSync(md)) fail('BUYER_QUERY_CONTENT_MATRIX.md missing');
  else pass('BUYER_QUERY_CONTENT_MATRIX.md present');

  let matrix;
  try {
    matrix = loadBuyerQueryMatrix(MARKETING_ROOT);
    pass('discoverability.buyer-query-matrix.json parses');
  } catch (e) {
    fail(e.message);
    matrix = { entries: [] };
  }
  const mErrs = validateBuyerQueryMatrixShape(matrix);
  if (mErrs.length) mErrs.forEach(fail);
  else pass(`buyer-query-matrix shape OK (${matrix.entries?.length ?? 0} entries)`);

  for (const q of D6_REQUIRED_MATRIX_QUERIES) {
    const hit = matrix.entries.some((e) => e.query === q && e.canonical_route);
    if (!hit) fail(`required query missing route mapping: ${q}`);
    else pass(`query mapped: ${q.length > 52 ? `${q.slice(0, 52)}…` : q}`);
  }

  gate('3] Evidence library registry');
  let reg;
  try {
    reg = loadEvidenceLibraryRegistry(MARKETING_ROOT);
    pass('discoverability.evidence-library-registry.json parses');
  } catch (e) {
    fail(e.message);
    reg = { pages: [] };
  }
  const rErrs = validateEvidenceLibraryRegistryShape(reg);
  if (rErrs.length) rErrs.forEach(fail);
  else pass(`evidence-library-registry shape OK (${reg.pages?.length ?? 0} pages)`);

  const mdReg = path.join(MARKETING_ROOT, 'EVIDENCE_LIBRARY_REGISTRY.md');
  if (!fs.existsSync(mdReg)) fail('EVIDENCE_LIBRARY_REGISTRY.md missing');
  else pass('EVIDENCE_LIBRARY_REGISTRY.md present');

  let entityReg;
  try {
    entityReg = loadEntitySemanticsRegistry(MARKETING_ROOT);
    pass('entity-semantics-registry.json parses');
  } catch (e) {
    fail(e.message);
    entityReg = null;
  }
  if (entityReg) {
    const esShape = validateEntitySemanticsRegistryShape(entityReg);
    if (esShape.length) esShape.forEach(fail);
    else pass('entity-semantics-registry shape OK');
    if (!fs.existsSync(path.join(MARKETING_ROOT, 'ENTITY_SEMANTICS_REGISTRY.md'))) {
      fail('ENTITY_SEMANTICS_REGISTRY.md missing (human registry)');
    } else pass('ENTITY_SEMANTICS_REGISTRY.md present');
  }

  const manifest = JSON.parse(
    fs.readFileSync(path.join(MARKETING_ROOT, 'discoverability.sitemap-manifest.json'), 'utf8'),
  );
  const staticPaths = new Set(manifest.staticPaths || []);

  gate('4] Core D6 routes — built HTML + sitemap manifest');
  for (const route of D6_CORE_EVIDENCE_ROUTES) {
    const html = readBuiltHtml(MARKETING_ROOT, route);
    if (!html) fail(`missing built HTML for ${route}`);
    else pass(`built HTML present: ${route}`);
    if (!staticPaths.has(route)) fail(`sitemap manifest missing static path: ${route}`);
    else pass(`sitemap manifest lists ${route}`);
  }

  gate('5] Evidence hub static structure + methodology links');
  const hubHtml = readBuiltHtml(MARKETING_ROOT, '/resources/evidence');
  if (!hubHtml) fail('hub HTML missing');
  else {
    const hErrs = validateD6EvidenceHubHtml(MARKETING_ROOT, hubHtml);
    if (hErrs.length) hErrs.forEach(fail);
    else pass('evidence hub markers + methodology links OK');
  }

  gate('6] Evidence detail — sections, proof anchors, capability honesty');
  for (const route of D6_CORE_EVIDENCE_ROUTES) {
    if (route === '/resources/evidence') continue;
    const html = readBuiltHtml(MARKETING_ROOT, route);
    if (!html) {
      fail(`missing detail HTML ${route}`);
      continue;
    }
    const e = validateD6EvidenceDetailHtml(MARKETING_ROOT, route, html);
    if (e.length) e.forEach(fail);
    else pass(`evidence detail OK: ${route}`);
  }

  gate('6b] Evidence detail — retrieval front-loading (first 30% of <main>)');
  for (const route of D6_CORE_EVIDENCE_ROUTES) {
    if (route === '/resources/evidence') continue;
    const html = readBuiltHtml(MARKETING_ROOT, route);
    if (!html) continue;
    const { errors, rows } = validateD6EvidenceFrontLoad(route, html);
    frontLoadReportRows.push(...rows);
    if (errors.length) errors.forEach(fail);
    else pass(`front-load OK: ${route}`);
  }
  printFrontLoadTable();

  gate('6c] Evidence detail — entity semantics drift (D4 registry binding)');
  if (entityReg) {
    for (const route of D6_CORE_EVIDENCE_ROUTES) {
      if (route === '/resources/evidence') continue;
      const html = readBuiltHtml(MARKETING_ROOT, route);
      if (!html) continue;
      const { errors, scan } = validateD6EntitySemanticsDrift(route, html, entityReg);
      entitySemanticsReportRows.push(scan);
      if (errors.length) errors.forEach(fail);
      else pass(`entity semantics OK: ${route}`);
    }
  }

  gate('6d] D6-b /methodology IP exposure and placeholder theater');
  const methodologyHtml = readBuiltHtml(MARKETING_ROOT, '/methodology');
  if (!methodologyHtml) {
    fail('missing built HTML for /methodology');
  } else {
    const mExp = validateD6MethodologyExposure(methodologyHtml);
    if (mExp.length) mExp.forEach(fail);
    else pass('/methodology D6-b exposure + structure OK');
  }

  gate('6e] D6-b /trust-envelope IP exposure and placeholder theater');
  const trustEnvelopeHtml = readBuiltHtml(MARKETING_ROOT, '/trust-envelope');
  if (!trustEnvelopeHtml) {
    fail('missing built HTML for /trust-envelope');
  } else {
    const teExp = validateD6TrustEnvelopeExposure(trustEnvelopeHtml);
    if (teExp.length) teExp.forEach(fail);
    else pass('/trust-envelope D6-b exposure + structure OK');
  }

  gate('6f] D6-b /revenue-verification IP exposure and placeholder theater');
  const revenueVerificationHtml = readBuiltHtml(MARKETING_ROOT, '/revenue-verification');
  if (!revenueVerificationHtml) {
    fail('missing built HTML for /revenue-verification');
  } else {
    const rvExp = validateD6RevenueVerificationExposure(revenueVerificationHtml);
    if (rvExp.length) rvExp.forEach(fail);
    else pass('/revenue-verification D6-b exposure + structure OK');
  }

  gate('6g] D6-b /attribution-methodology IP exposure and placeholder theater');
  const attributionMethodologyHtml = readBuiltHtml(MARKETING_ROOT, '/attribution-methodology');
  if (!attributionMethodologyHtml) {
    fail('missing built HTML for /attribution-methodology');
  } else {
    const amExp = validateD6AttributionMethodologyExposure(attributionMethodologyHtml);
    if (amExp.length) amExp.forEach(fail);
    else pass('/attribution-methodology D6-b exposure + structure OK');
  }

  gate('6h] D6-b /discrepancy-taxonomy IP exposure and placeholder theater');
  const discrepancyTaxonomyHtml = readBuiltHtml(MARKETING_ROOT, '/discrepancy-taxonomy');
  if (!discrepancyTaxonomyHtml) {
    fail('missing built HTML for /discrepancy-taxonomy');
  } else {
    const dtExp = validateD6DiscrepancyTaxonomyExposure(discrepancyTaxonomyHtml);
    if (dtExp.length) dtExp.forEach(fail);
    else pass('/discrepancy-taxonomy D6-b exposure + structure OK');
  }

  gate('6i] D6-b /ai-boundary IP exposure and placeholder theater');
  const aiBoundaryHtml = readBuiltHtml(MARKETING_ROOT, '/ai-boundary');
  if (!aiBoundaryHtml) {
    fail('missing built HTML for /ai-boundary');
  } else {
    const aiExp = validateD6AiBoundaryExposure(aiBoundaryHtml);
    if (aiExp.length) aiExp.forEach(fail);
    else pass('/ai-boundary D6-b exposure + structure OK');
  }

  gate('6j] D6-b /security IP exposure, overclaim, and placeholder theater');
  const securityHtml = readBuiltHtml(MARKETING_ROOT, '/security');
  if (!securityHtml) {
    fail('missing built HTML for /security');
  } else {
    const secExp = validateD6SecurityExposure(securityHtml);
    if (secExp.length) secExp.forEach(fail);
    else pass('/security D6-b exposure + structure OK');
  }

  gate('6k] D6-b /status designed-absence and registry alignment');
  const statusHtml = readBuiltHtml(MARKETING_ROOT, '/status');
  let statusRegistry;
  try {
    statusRegistry = loadStatusRegistry(MARKETING_ROOT);
    pass('discoverability.status-registry.json parses');
  } catch (e) {
    fail(e.message);
    statusRegistry = { active_incidents: [], scheduled_maintenance: [], sitemap_required: true };
  }
  if (!statusHtml) {
    fail('missing built HTML for /status');
  } else {
    const stExp = validateD6StatusExposure(statusHtml, statusRegistry, {
      sitemapPaths: staticPaths,
    });
    if (stExp.length) stExp.forEach(fail);
    else pass('/status D6-b designed-absence + registry OK');
  }

  gate('6l] D6-b /press designed-absence, contacts, and IP boundary');
  const pressHtml = readBuiltHtml(MARKETING_ROOT, '/press');
  let pressRegistry;
  let contactsRegistry;
  try {
    pressRegistry = loadPressRegistry(MARKETING_ROOT);
    pass('discoverability.press-registry.json parses');
  } catch (e) {
    fail(e.message);
    pressRegistry = { indexability: true, sitemap_required: true, approved_media_claims: [] };
  }
  try {
    contactsRegistry = loadPublicContactsRegistry(MARKETING_ROOT);
    pass('discoverability.public-contacts.json parses');
  } catch (e) {
    fail(e.message);
    contactsRegistry = { contacts: [] };
  }
  if (!pressHtml) {
    fail('missing built HTML for /press');
  } else {
    const prExp = validateD6PressExposure(pressHtml, contactsRegistry, pressRegistry, {
      sitemapPaths: staticPaths,
    });
    if (prExp.length) prExp.forEach(fail);
    else pass('/press D6-b designed-absence + contacts OK');
  }

  gate('6m] D6-b /careers designed-absence, contacts, and IP boundary');
  const careersHtml = readBuiltHtml(MARKETING_ROOT, '/careers');
  let careersRegistry;
  let careersContactsRegistry;
  try {
    careersRegistry = loadCareersRegistry(MARKETING_ROOT);
    pass('discoverability.careers-registry.json parses');
  } catch (e) {
    fail(e.message);
    careersRegistry = {
      active_roles_count: 0,
      talent_contact_channel: 'engineering@skeldir.com',
      contact_approved: true,
      indexability: true,
      sitemap_required: true,
      job_posting_allowed: false,
      approved_benefit_claims: [],
    };
  }
  try {
    careersContactsRegistry = loadPublicContactsForCareers(MARKETING_ROOT);
  } catch (e) {
    fail(e.message);
    careersContactsRegistry = { contacts: [] };
  }
  if (!careersHtml) {
    fail('missing built HTML for /careers');
  } else {
    const carExp = validateD6CareersExposure(
      careersHtml,
      careersRegistry,
      careersContactsRegistry,
      { sitemapPaths: staticPaths },
    );
    if (carExp.length) carExp.forEach(fail);
    else pass('/careers D6-b designed-absence + registry OK');
  }

  const footerPath = path.join(MARKETING_ROOT, 'src', 'components', 'layout', 'Footer.tsx');
  if (fs.existsSync(footerPath)) {
    const footerSrc = fs.readFileSync(footerPath, 'utf8');
    if (/label:\s*["']Careers["'][^}]*href:\s*["']\/careers["']/i.test(footerSrc)) {
      pass('Footer.tsx: Careers → /careers');
    } else {
      fail('Footer.tsx: Careers label must href="/careers"');
    }
    if (/label:\s*["']Careers["'][^}]*href:\s*["']\/resources["']/i.test(footerSrc)) {
      fail('Footer.tsx: Careers must not point to /resources');
    } else {
      pass('Footer.tsx: Careers does not point to /resources');
    }
  }

  gate('6n] D6-b /api access boundary, contract leakage, and contacts');
  const apiHtml = readBuiltHtml(MARKETING_ROOT, '/api');
  let apiSurfaceRegistry;
  let apiContactsRegistry;
  try {
    apiSurfaceRegistry = loadApiSurfaceRegistry(MARKETING_ROOT);
    pass('discoverability.api-surface-registry.json parses');
  } catch (e) {
    fail(e.message);
    apiSurfaceRegistry = {
      public_api_reference_available: false,
      public_endpoint_details_rendered: false,
      contact_channel: 'sales@skeldir.com',
      contact_approved: true,
      indexability: true,
      sitemap_required: true,
      required_boundary_phrases: [],
    };
  }
  try {
    apiContactsRegistry = loadPublicContactsForApi(MARKETING_ROOT);
  } catch (e) {
    fail(e.message);
    apiContactsRegistry = { contacts: [] };
  }
  if (!apiHtml) {
    fail('missing built HTML for /api');
  } else {
    const apiExp = validateD6ApiExposure(apiHtml, apiSurfaceRegistry, apiContactsRegistry, {
      sitemapPaths: staticPaths,
    });
    if (apiExp.length) apiExp.forEach(fail);
    else pass('/api D6-b access boundary + registry OK');
  }

  gate('6o] D6-b /privacy posture, IP leakage, overclaim, and contacts');
  const privacyHtml = readBuiltHtml(MARKETING_ROOT, '/privacy');
  let privacySurfaceRegistry;
  let privacyContactsRegistry;
  try {
    privacySurfaceRegistry = loadPrivacySurfaceRegistry(MARKETING_ROOT);
    pass('discoverability.privacy-surface-registry.json parses');
  } catch (e) {
    fail(e.message);
    privacySurfaceRegistry = {
      public_page_type: 'privacy_posture',
      legal_review_status: 'pending',
      indexability: false,
      sitemap_required: false,
      contact_channels: ['engineering@skeldir.com', 'security@skeldir.com'],
      contact_approved: true,
      required_boundary_phrases: [],
    };
  }
  try {
    privacyContactsRegistry = loadPublicContactsForPrivacy(MARKETING_ROOT);
  } catch (e) {
    fail(e.message);
    privacyContactsRegistry = { contacts: [] };
  }
  if (!privacyHtml) {
    fail('missing built HTML for /privacy');
  } else {
    const privExp = validateD6PrivacyExposure(
      privacyHtml,
      privacySurfaceRegistry,
      privacyContactsRegistry,
      { sitemapPaths: staticPaths },
    );
    if (privExp.length) privExp.forEach(fail);
    else pass('/privacy D6-b privacy posture + registry OK');
  }

  gate('6p] D6-b /about entity positioning, IP exposure, and semantics');
  const aboutHtml = readBuiltHtml(MARKETING_ROOT, '/about');
  let aboutSurfaceRegistry;
  try {
    aboutSurfaceRegistry = loadAboutSurfaceRegistry(MARKETING_ROOT);
    pass('discoverability.about-surface-registry.json parses');
  } catch (e) {
    fail(e.message);
    aboutSurfaceRegistry = {
      indexability: true,
      sitemap_required: true,
      required_boundary_phrases: [],
      approved_positioning_terms: [],
    };
  }
  if (!aboutHtml) {
    fail('missing built HTML for /about');
  } else {
    const aboutExp = validateD6AboutExposure(aboutHtml, aboutSurfaceRegistry, {
      sitemapPaths: staticPaths,
      marketingRoot: MARKETING_ROOT,
    });
    if (aboutExp.length) aboutExp.forEach(fail);
    else pass('/about D6-b entity page + registry OK');
  }

  gate('7] /resources hub links to evidence library');
  const resHtml = readBuiltHtml(MARKETING_ROOT, '/resources');
  if (!resHtml || !resHtml.includes('href="/resources/evidence"')) {
    fail('/resources built HTML must link to /resources/evidence');
  } else pass('/resources → /resources/evidence anchor present');

  gate('8] Registry indexable routes ⊆ sitemap manifest');
  for (const p of reg.pages || []) {
    if (!p.indexable) continue;
    if (!staticPaths.has(p.route)) {
      fail(`registry indexable route missing from sitemap manifest: ${p.route}`);
    } else pass(`registry route in manifest: ${p.route}`);
  }

  gate('9] All-pairs evidence similarity (anti-spam)');
  const { rows, errors } = computeEvidenceAllPairsSimilarity(
    MARKETING_ROOT,
    (route) => readBuiltHtml(MARKETING_ROOT, route),
    D6_CORE_EVIDENCE_ROUTES,
  );
  similarityReportRows.push(...rows);
  const hardFails = rows.filter((r) => r.result === 'fail');
  const warns = rows.filter((r) => r.result === 'warn');
  console.log(`  Pairs measured: ${rows.length}; hard failures: ${hardFails.length}; soft warnings: ${warns.length}`);
  if (errors.length) errors.forEach(fail);
  else pass('all-pairs similarity within hard threshold (or overridden)');

  gate('10] Global release status note');
  pass(
    'D6 production-final remains BLOCKED_BY_GLOBAL_RELEASE until mainline Git lineage, mergeable-branch CI, deploy preview, and production-equivalent curls are green (directive §6 / §8).',
  );

  const reportPath = path.join(MARKETING_ROOT, 'discoverability.d6-frontload-report.json');
  fs.writeFileSync(
    reportPath,
    JSON.stringify(
      {
        generatedAt: new Date().toISOString(),
        frontLoad: frontLoadReportRows,
        entitySemantics: entitySemanticsReportRows,
        similarity: similarityReportRows,
      },
      null,
      2,
    ),
  );
  pass(`wrote harness artifact ${path.basename(reportPath)}`);

  console.log('\n──────────────────────────────────────────────');
  console.log(`Passes: ${passes}  Failures: ${failures}`);
  if (failures > 0) process.exit(1);
}

main();
