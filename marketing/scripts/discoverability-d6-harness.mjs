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
  D6_PLATFORM_PAIR_ROUTES,
  D6_REQUIRED_MATRIX_QUERIES,
  extractEvidenceTextForSimilarity,
  jaccardWordSimilarity,
  loadBuyerQueryMatrix,
  loadEvidenceLibraryRegistry,
  loadSimilarityOverrides,
  validateBuyerQueryMatrixShape,
  validateD6EvidenceDetailHtml,
  validateD6EvidenceHubHtml,
  validateEvidenceLibraryRegistryShape,
} from './discoverability/lib/d6-evidence-library.mjs';

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

  gate('5] Evidence hub static structure');
  const hubHtml = readBuiltHtml(MARKETING_ROOT, '/resources/evidence');
  if (!hubHtml) fail('hub HTML missing');
  else {
    const hErrs = validateD6EvidenceHubHtml(MARKETING_ROOT, hubHtml);
    if (hErrs.length) hErrs.forEach(fail);
    else pass('evidence hub markers + D5 links OK');
  }

  gate('6] Evidence detail pages — sections / D5 proof anchors');
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

  gate('9] Platform pair similarity (anti-spam)');
  const ha = readBuiltHtml(MARKETING_ROOT, D6_PLATFORM_PAIR_ROUTES[0]);
  const hb = readBuiltHtml(MARKETING_ROOT, D6_PLATFORM_PAIR_ROUTES[1]);
  if (!ha || !hb) fail('platform pair HTML missing');
  else {
    const ta = extractEvidenceTextForSimilarity(ha);
    const tb = extractEvidenceTextForSimilarity(hb);
    const sim = jaccardWordSimilarity(ta, tb);
    console.log(`  Meta vs Google Ads similarity (Jaccard on de-boilerplated tokens): ${sim.toFixed(3)}`);
    const overrides = loadSimilarityOverrides(MARKETING_ROOT).pair_overrides || [];
    const hasOverride = overrides.some((o) => o.pair === 'meta-vs-stripe|google-ads-vs-shopify' && o.justification);
    const hard = 0.85;
    const soft = 0.72;
    if (sim >= hard && !hasOverride) {
      fail(`platform pages too similar (>= ${hard}) without manual override`);
    } else if (sim >= soft) {
      pass(`similarity ${sim.toFixed(3)} ≥ soft ${soft} — document distinctiveness or add override entry if intentional`);
    } else pass(`similarity ${sim.toFixed(3)} < soft ${soft}`);
  }

  gate('10] Global release status note');
  pass(
    'D6 production-final remains BLOCKED_BY_GLOBAL_RELEASE until mainline Git lineage, mergeable-branch CI, deploy preview, and production-equivalent curls are green (directive §6 / §8).',
  );

  console.log('\n──────────────────────────────────────────────');
  console.log(`Passes: ${passes}  Failures: ${failures}`);
  if (failures > 0) process.exit(1);
}

main();
