#!/usr/bin/env node

/**
 * Skeldir D5 — Trust Proof Boundary and Legal/Security Surface harness.
 *
 * Gates:
 *   D5.1 Legal and security route integrity
 *   D5.2 Claim-proof registry completeness
 *   D5.3 TrustEnvelope proof page concepts
 *   D5.4 Methodology + AI boundary concepts
 *   D5.5 Revenue verification / attribution / discrepancy concepts
 *   D5.6 Legal/security honesty boundary (no invented certifications)
 *   D5.7 Static HTML + indexability for proof pages
 *   D5.8 Local phase vs production closure separation (reported)
 *
 * Usage:
 *   npm run discoverability:d5
 *   MARKETING_D5_SKIP_BUILD=1 npm run discoverability:d5   # reuses out/
 */

import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

import {
  D5_INDEXABLE_PROOF_ROUTES,
  D5_LEGAL_PLACEHOLDER_ROUTES,
  D5_RESERVED_DOC_PLACEHOLDER_ROUTES,
  D5_REQUIRED_ROUTES,
  D5_HIGH_STAKES_CLAIM_TRIGGERS,
  D5_REQUIRED_CONCEPTS,
  discoverAppRouterRoutes,
  readBuiltHtml,
  scanHighStakesClaimSources,
  scanInventedComplianceClaims,
  validateBookDemoPrivacyLink,
  validateClaimProofAnchorsExist,
  validateClaimProofRegistryShape,
  validateD5LegalPlaceholder,
  validateD5ProofPageBaseline,
  validateD5ProofPageConcepts,
  validateFooterLegalLinkPolicy,
  loadClaimProofRegistry,
} from './discoverability/lib/d5-trust-proof.mjs';

const MARKETING_ROOT = process.cwd();

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

function ensureBuild() {
  const skip =
    process.env.MARKETING_D5_SKIP_BUILD === '1' || process.argv.includes('--skip-build');
  if (skip) {
    const idx = path.join(MARKETING_ROOT, 'out', 'index.html');
    if (!fs.existsSync(idx)) {
      fail('MARKETING_D5_SKIP_BUILD=1 but out/index.html is missing — run npm run build first');
      process.exit(1);
    }
    pass('npm run build skipped (MARKETING_D5_SKIP_BUILD=1 or --skip-build); using existing out/');
    return;
  }
  const b = spawnSync('npm run build', { cwd: MARKETING_ROOT, shell: true, stdio: 'inherit' });
  if (b.status !== 0) {
    fail('npm run build exited non-zero');
    process.exit(1);
  }
  pass('npm run build completed');
}

function gateHeader(name) {
  console.log(`\n[${name}]`);
}

function main() {
  console.log('╔══════════════════════════════════════════════════════════╗');
  console.log('║  Skeldir D5 — Trust Proof Boundary and Legal/Security    ║');
  console.log('╚══════════════════════════════════════════════════════════╝\n');

  gateHeader('0] Production build');
  ensureBuild();

  gateHeader('D5.1] Required D5 routes exist as source');
  const appRoutes = discoverAppRouterRoutes(MARKETING_ROOT);
  for (const r of D5_REQUIRED_ROUTES) {
    if (appRoutes.has(r)) pass(`route source present: ${r}`);
    else fail(`required D5 route missing from src/app: ${r}`);
  }

  gateHeader('D5.1] Required D5 routes exist as built HTML');
  for (const r of D5_REQUIRED_ROUTES) {
    const html = readBuiltHtml(MARKETING_ROOT, r);
    if (html === null) fail(`required D5 route has no built HTML in out/: ${r}`);
    else pass(`built HTML present: ${r}`);
  }

  gateHeader('D5.1] Legal placeholder routes — explicit status + noindex');
  for (const r of D5_LEGAL_PLACEHOLDER_ROUTES) {
    const html = readBuiltHtml(MARKETING_ROOT, r);
    if (html === null) {
      fail(`legal placeholder ${r}: built HTML missing`);
      continue;
    }
    const errs = validateD5LegalPlaceholder(MARKETING_ROOT, r, html);
    if (errs.length === 0) pass(`legal placeholder ${r} OK`);
    else errs.forEach((e) => fail(e));
  }

  gateHeader('D5.1] Footer/legal/proof link policy');
  const footerErrs = validateFooterLegalLinkPolicy(MARKETING_ROOT);
  if (footerErrs.length === 0) pass('Footer.tsx: all required legal/proof links wired correctly');
  else footerErrs.forEach((e) => fail(e));

  gateHeader('D5.1] Book-demo /privacy link resolves');
  const bdErrs = validateBookDemoPrivacyLink(MARKETING_ROOT);
  if (bdErrs.length === 0) pass('book-demo Privacy Policy link resolves to /privacy');
  else bdErrs.forEach((e) => fail(e));

  gateHeader('D5.2] Claim-proof registry shape');
  const shapeErrs = validateClaimProofRegistryShape(MARKETING_ROOT);
  if (shapeErrs.length === 0) pass('claim-proof registry shape OK');
  else shapeErrs.forEach((e) => fail(e));

  gateHeader('D5.2] Claim-proof anchors exist in built HTML');
  const anchorErrs = validateClaimProofAnchorsExist(MARKETING_ROOT);
  if (anchorErrs.length === 0) pass('every registered claim anchor exists in built HTML');
  else anchorErrs.forEach((e) => fail(e));

  gateHeader('D5.2] High-stakes claim triggers covered by registry');
  let registry;
  try {
    registry = loadClaimProofRegistry(MARKETING_ROOT);
  } catch (e) {
    fail(e.message);
    registry = { claims: [] };
  }
  const triggerHits = scanHighStakesClaimSources(MARKETING_ROOT);
  const claimText = registry.claims.map((c) => String(c.claim_text || '').toLowerCase()).join('\n');
  const claimCategoryCoverage = new Set(registry.claims.map((c) => c.claim_category));
  /**
   * Trigger → required category mapping. A trigger word counts as covered
   * if either (a) its registered category appears in the registry or
   * (b) the trigger phrase literally appears inside some registered
   * claim_text.
   */
  const triggerCategoryMap = {
    verified: 'revenue_verification',
    deterministic: 'deterministic_truth',
    'financial truth': 'deterministic_truth',
    TrustEnvelope: 'trust_envelope',
    'source of truth': 'auditability',
    audit: 'auditability',
    'no PII': 'privacy_no_pii',
    'commerce evidence': 'revenue_verification',
    'policy authority': 'trust_envelope',
    'AI Agents': 'ai_boundary',
  };
  for (const trigger of D5_HIGH_STAKES_CLAIM_TRIGGERS) {
    const hits = triggerHits[trigger] || [];
    if (hits.length === 0) {
      pass(`trigger "${trigger}" not present in source — nothing to cover`);
      continue;
    }
    const requiredCategory = triggerCategoryMap[trigger];
    const coveredByCategory = requiredCategory && claimCategoryCoverage.has(requiredCategory);
    const coveredByText = claimText.includes(trigger.toLowerCase());
    if (coveredByCategory || coveredByText) {
      pass(
        `trigger "${trigger}" present in ${hits.length} file(s) and covered by registry (${requiredCategory || 'text match'})`,
      );
    } else {
      fail(
        `trigger "${trigger}" present in source files [${hits.slice(0, 3).join(', ')}${hits.length > 3 ? ', …' : ''}] but no claim with category "${requiredCategory}" or text match in registry`,
      );
    }
  }

  gateHeader('D5.3 / D5.4 / D5.5] Required concept markers on every proof page');
  for (const route of D5_INDEXABLE_PROOF_ROUTES) {
    if (!D5_REQUIRED_CONCEPTS[route]) continue;
    const html = readBuiltHtml(MARKETING_ROOT, route);
    if (html === null) {
      fail(`${route}: built HTML missing for concept check`);
      continue;
    }
    const errs = validateD5ProofPageConcepts(route, html);
    if (errs.length === 0)
      pass(`${route}: contains every required concept marker (${D5_REQUIRED_CONCEPTS[route].length})`);
    else errs.forEach((e) => fail(e));
  }

  gateHeader('D5.6] Legal/security honesty boundary (no invented compliance phrases)');
  const sourceRootsForBanScan = [
    path.join(MARKETING_ROOT, 'src', 'app'),
    path.join(MARKETING_ROOT, 'src', 'components'),
  ];
  /** @type {string[]} */
  const sourceFiles = [];
  for (const r of sourceRootsForBanScan) {
    /** @param {string} d */
    (function walk(d) {
      if (!fs.existsSync(d)) return;
      for (const ent of fs.readdirSync(d, { withFileTypes: true })) {
        const p = path.join(d, ent.name);
        if (ent.isDirectory()) {
          if (ent.name.startsWith('_') || ent.name === 'node_modules') continue;
          walk(p);
        } else if (/\.(tsx|ts|jsx|js|md|mdx)$/.test(ent.name)) {
          sourceFiles.push(p);
        }
      }
    })(r);
  }
  let banned = 0;
  for (const f of sourceFiles) {
    const html = fs.readFileSync(f, 'utf8');
    const hits = scanInventedComplianceClaims(html);
    if (hits.length > 0) {
      for (const h of hits) {
        fail(
          `${path.relative(MARKETING_ROOT, f).replace(/\\/g, '/')} contains banned compliance phrase "${h}" — register the claim as operator_approved with cited evidence or remove`,
        );
        banned++;
      }
    }
  }
  if (banned === 0) pass(`scanned ${sourceFiles.length} source files — no invented compliance claims`);

  gateHeader('D5.7] Static HTML + indexability baseline for every proof page');
  for (const route of D5_INDEXABLE_PROOF_ROUTES) {
    const html = readBuiltHtml(MARKETING_ROOT, route);
    if (html === null) {
      fail(`${route}: built HTML missing for baseline check`);
      continue;
    }
    const errs = validateD5ProofPageBaseline(MARKETING_ROOT, route, html);
    if (errs.length === 0) pass(`${route}: baseline OK (H1, canonical, review status, indexable, static body)`);
    else errs.forEach((e) => fail(e));
  }

  gateHeader('D5.7] Sitemap manifest includes every indexable proof route');
  const manifest = JSON.parse(
    fs.readFileSync(path.join(MARKETING_ROOT, 'discoverability.sitemap-manifest.json'), 'utf8'),
  );
  const inSitemap = new Set(manifest.staticPaths || []);
  for (const r of D5_INDEXABLE_PROOF_ROUTES) {
    if (inSitemap.has(r)) pass(`sitemap manifest includes ${r}`);
    else fail(`sitemap manifest must include indexable proof route ${r}`);
  }
  for (const r of D5_LEGAL_PLACEHOLDER_ROUTES) {
    if (inSitemap.has(r)) {
      fail(
        `sitemap manifest must NOT include legal placeholder ${r} until operator approves indexable copy`,
      );
    } else pass(`sitemap manifest correctly excludes legal placeholder ${r}`);
  }
  for (const r of D5_RESERVED_DOC_PLACEHOLDER_ROUTES) {
    if (inSitemap.has(r)) {
      fail(`sitemap manifest must NOT include reserved placeholder ${r}`);
    } else pass(`sitemap manifest correctly excludes reserved placeholder ${r}`);
  }

  gateHeader('D5.8] Local phase vs production closure separation (informational)');
  warn(
    'D5 LOCAL proof state is what this harness asserts. Production-final closure additionally requires: mainline Git lineage resolved, CI green, deploy-preview proof, production curl proof for D5 routes. Carry this forward in the D5 completion report.',
  );

  console.log('\n──────────────────────────────────────────────────────────');
  console.log(`Passes: ${passes}  Warnings: ${warnings}  Failures: ${failures}`);
  if (failures > 0) process.exit(1);
}

main();
