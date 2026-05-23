#!/usr/bin/env node

/**
 * Skeldir D5 negative controls.
 *
 * Each control asserts that a deliberately broken fixture is caught by
 * the D5 validators. We construct fixtures in-memory rather than mutating
 * the real source tree.
 */

import fs from 'node:fs';
import path from 'node:path';

import {
  D5_INDEXABLE_PROOF_ROUTES,
  D5_LEGAL_PLACEHOLDER_ROUTES,
  D5_BANNED_UNAPPROVED_COMPLIANCE_PHRASES,
  D5_REQUIRED_CONCEPTS,
  readBuiltHtml,
  scanInventedComplianceClaims,
  validateD5LegalPlaceholder,
  validateD5ProofPageBaseline,
  validateD5ProofPageConcepts,
  validateFooterLegalLinkPolicy,
  validateClaimProofRegistryShape,
} from './discoverability/lib/d5-trust-proof.mjs';

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

function expectErrors(label, errs, min = 1) {
  if (Array.isArray(errs) && errs.length >= min) {
    pass(`${label} → detected ${errs.length} issue(s)`);
    return true;
  }
  fail(`${label} → expected ≥${min} error(s), got ${errs?.length ?? 0}`);
  return false;
}

function readTextOr(path, fallback) {
  try {
    return fs.readFileSync(path, 'utf8');
  } catch {
    return fallback;
  }
}

function patchHtml(html, patcher) {
  return patcher(html);
}

function main() {
  console.log('╔══════════════════════════════════════════════════════════╗');
  console.log('║  Skeldir D5 — Negative control proof                     ║');
  console.log('╚══════════════════════════════════════════════════════════╝\n');

  /**
   * NC-D5-01 — Footer Privacy → /resources must fail.
   * We synthesize a Footer source string in-memory rather than mutate the
   * real file. Then we invoke the same validator via a temp file.
   */
  console.log('\n[NC-D5-01] Footer Privacy → /resources is caught');
  const tmpDir = fs.mkdtempSync(path.join(MARKETING_ROOT, '.d5-neg-'));
  try {
    const tmpSrc = path.join(tmpDir, 'src', 'components', 'layout');
    fs.mkdirSync(tmpSrc, { recursive: true });
    const badFooter = `
      const legalLinks = [
        { label: "Privacy Policy", href: "/resources" },
        { label: "Terms of Service", href: "/terms" },
        { label: "GDPR", href: "/gdpr" },
        { label: "Security", href: "/security" },
      ];
      const trust = [
        { label: "Methodology", href: "/methodology" },
        { label: "TrustEnvelope", href: "/trust-envelope" },
        { label: "Documentation", href: "/docs" },
        { label: "API Reference", href: "/api" },
      ];
    `;
    fs.writeFileSync(path.join(tmpSrc, 'Footer.tsx'), badFooter, 'utf8');
    const errs = validateFooterLegalLinkPolicy(tmpDir);
    expectErrors('NC-D5-01 footer Privacy → /resources', errs, 1);
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }

  /**
   * NC-D5-02 — Footer missing a required label must fail.
   */
  console.log('\n[NC-D5-02] Footer missing required Methodology label is caught');
  {
    const tmpDir2 = fs.mkdtempSync(path.join(MARKETING_ROOT, '.d5-neg-'));
    try {
      fs.mkdirSync(path.join(tmpDir2, 'src', 'components', 'layout'), { recursive: true });
      const footerMissing = `
        const legalLinks = [
          { label: "Privacy Policy", href: "/privacy" },
          { label: "Terms of Service", href: "/terms" },
          { label: "GDPR", href: "/gdpr" },
          { label: "Security", href: "/security" },
        ];
        const support = [
          { label: "Documentation", href: "/docs" },
          { label: "API Reference", href: "/api" },
        ];
      `;
      fs.writeFileSync(
        path.join(tmpDir2, 'src', 'components', 'layout', 'Footer.tsx'),
        footerMissing,
        'utf8',
      );
      const errs = validateFooterLegalLinkPolicy(tmpDir2);
      expectErrors('NC-D5-02 footer missing Methodology label', errs, 1);
    } finally {
      fs.rmSync(tmpDir2, { recursive: true, force: true });
    }
  }

  /**
   * NC-D5-03 — Proof page emits a Loading shell must fail.
   */
  console.log('\n[NC-D5-03] Proof page Loading shell is caught');
  {
    const fakeHtml = `
      <html><head><title>T</title>
      <link rel="canonical" href="https://skeldir.com/methodology"/>
      <meta name="description" content="x"/>
      </head><body><div class="animate-pulse">Loading...</div></body></html>
    `;
    const errs = validateD5ProofPageBaseline(MARKETING_ROOT, '/methodology', fakeHtml);
    expectErrors('NC-D5-03 proof page Loading shell', errs, 1);
  }

  /**
   * NC-D5-04 — Proof page noindex (when it should be indexable) must fail.
   */
  console.log('\n[NC-D5-04] Proof page accidentally noindex is caught');
  {
    const html = `
      <html><head>
      <title>T</title>
      <meta name="description" content="d"/>
      <link rel="canonical" href="https://skeldir.com/methodology"/>
      <meta name="robots" content="noindex, follow"/>
      </head><body><h1>Methodology</h1><p>operator_approved</p><p>Last reviewed: 2026-05-23</p></body></html>
    `;
    const errs = validateD5ProofPageBaseline(MARKETING_ROOT, '/methodology', html);
    expectErrors('NC-D5-04 proof page noindex', errs, 1);
  }

  /**
   * NC-D5-05 — Proof page missing review-status token must fail.
   */
  console.log('\n[NC-D5-05] Proof page missing review-status token is caught');
  {
    const html = `
      <html><head>
      <title>T</title>
      <meta name="description" content="d"/>
      <link rel="canonical" href="https://skeldir.com/methodology"/>
      </head><body><h1>Methodology</h1><p>Last reviewed: 2026-05-23</p></body></html>
    `;
    const errs = validateD5ProofPageBaseline(MARKETING_ROOT, '/methodology', html);
    expectErrors('NC-D5-05 proof page missing review-status token', errs, 1);
  }

  /**
   * NC-D5-07 — Trust envelope page missing "semantic truth hash" concept fails.
   */
  console.log('\n[NC-D5-07] /trust-envelope missing required concept "semantic truth hash" is caught');
  {
    const html = `
      <html><head><title>T</title></head>
      <body>
        <h1>TrustEnvelope</h1>
        <p>deterministic values, provenance chain, artifact hash, confidence status, benchmark metadata, policy authority, fallback reason, external verification metadata, action authority, audit trail, limitations</p>
      </body></html>
    `;
    const errs = validateD5ProofPageConcepts('/trust-envelope', html);
    expectErrors('NC-D5-07 /trust-envelope missing semantic truth hash', errs, 1);
  }

  /**
   * NC-D5-08 — Methodology page missing AI boundary concept fails.
   */
  console.log('\n[NC-D5-08] /methodology missing AI boundary signals is caught');
  {
    const html = `
      <html><head><title>T</title></head>
      <body>
        <h1>Methodology</h1>
        <p>verified evidence, attribution model, discrepancy, limitations, last reviewed</p>
      </body></html>
    `;
    const errs = validateD5ProofPageConcepts('/methodology', html);
    expectErrors('NC-D5-08 /methodology missing "deterministic" concept', errs, 1);
  }

  /**
   * NC-D5-09 — Security page claiming SOC 2 without approved evidence is caught.
   */
  console.log('\n[NC-D5-09] Security page claiming SOC 2 certified is caught');
  {
    const html = '<html><body>Skeldir is SOC 2 certified and HIPAA compliant.</body></html>';
    const hits = scanInventedComplianceClaims(html);
    expectErrors('NC-D5-09 SOC 2 / HIPAA invented claim', hits, 1);
  }

  /**
   * NC-D5-10 — Legal placeholder /privacy missing legal_review_required status is caught.
   */
  console.log('\n[NC-D5-10] /privacy missing legal_review_required is caught');
  {
    const html = `
      <html><head>
      <title>Privacy</title>
      <meta name="description" content="x"/>
      <link rel="canonical" href="https://skeldir.com/privacy"/>
      <meta name="robots" content="noindex"/>
      </head><body><h1>Privacy</h1><p>Generic placeholder text without status.</p></body></html>
    `;
    const errs = validateD5LegalPlaceholder(MARKETING_ROOT, '/privacy', html);
    expectErrors('NC-D5-10 /privacy missing legal_review_required', errs, 1);
  }

  /**
   * NC-D5-11 — Legal placeholder /privacy missing noindex is caught.
   */
  console.log('\n[NC-D5-11] /privacy missing noindex while legal_review_required is caught');
  {
    const html = `
      <html><head>
      <title>Privacy</title>
      <meta name="description" content="x"/>
      <link rel="canonical" href="https://skeldir.com/privacy"/>
      </head><body><h1>Privacy</h1><p>legal_review_required placeholder.</p></body></html>
    `;
    const errs = validateD5LegalPlaceholder(MARKETING_ROOT, '/privacy', html);
    expectErrors('NC-D5-11 /privacy missing noindex', errs, 1);
  }

  /**
   * NC-D5-12 — Claim registry missing required field is caught.
   */
  console.log('\n[NC-D5-12] Claim registry missing required field is caught');
  {
    const tmpDir3 = fs.mkdtempSync(path.join(MARKETING_ROOT, '.d5-neg-'));
    try {
      fs.writeFileSync(
        path.join(tmpDir3, 'discoverability.claim-proof-registry.json'),
        JSON.stringify({
          claims: [
            {
              claim_id: 'BAD-1',
              claim_text: 'something',
            },
          ],
        }),
        'utf8',
      );
      const errs = validateClaimProofRegistryShape(tmpDir3);
      expectErrors('NC-D5-12 claim registry missing fields', errs, 1);
    } finally {
      fs.rmSync(tmpDir3, { recursive: true, force: true });
    }
  }

  /**
   * NC-D5-13 — Claim with bogus category is caught.
   */
  console.log('\n[NC-D5-13] Claim with unknown category is caught');
  {
    const tmpDir4 = fs.mkdtempSync(path.join(MARKETING_ROOT, '.d5-neg-'));
    try {
      fs.writeFileSync(
        path.join(tmpDir4, 'discoverability.claim-proof-registry.json'),
        JSON.stringify({
          claims: [
            {
              claim_id: 'BAD-2',
              claim_text: 'X',
              source_route: '/',
              source_component_or_file: 'src/x.tsx',
              claim_category: 'totally_made_up',
              risk_level: 'high',
              proof_route: '/methodology',
              proof_anchor: '#anchor',
              proof_type: 'methodology_disclosure',
              owner: 'team',
              legal_review_required: false,
              status: 'operator_approved',
              last_reviewed: '2026-05-23',
            },
          ],
        }),
        'utf8',
      );
      const errs = validateClaimProofRegistryShape(tmpDir4);
      expectErrors('NC-D5-13 claim with unknown category', errs, 1);
    } finally {
      fs.rmSync(tmpDir4, { recursive: true, force: true });
    }
  }

  /**
   * NC-D5-14 — Real built proof pages must still pass their concept gates.
   * This is a regression check: confirm we did not weaken the real pages.
   */
  console.log('\n[NC-D5-14] Real built pages still pass concept gates (regression)');
  let regression = 0;
  for (const route of D5_INDEXABLE_PROOF_ROUTES) {
    const html = readBuiltHtml(MARKETING_ROOT, route);
    if (html === null) continue;
    const errs = validateD5ProofPageConcepts(route, html);
    if (errs.length > 0) {
      regression++;
      errs.forEach((e) => fail(`regression: ${e}`));
    }
  }
  if (regression === 0) pass('all real proof pages still satisfy their concept gates');

  /**
   * NC-D5-15 — Real legal placeholder pages still pass their placeholder gate.
   */
  console.log('\n[NC-D5-15] Real legal placeholder pages still pass placeholder gate (regression)');
  let lpr = 0;
  for (const route of D5_LEGAL_PLACEHOLDER_ROUTES) {
    const html = readBuiltHtml(MARKETING_ROOT, route);
    if (html === null) continue;
    const errs = validateD5LegalPlaceholder(MARKETING_ROOT, route, html);
    if (errs.length > 0) {
      lpr++;
      errs.forEach((e) => fail(`regression: ${e}`));
    }
  }
  if (lpr === 0) pass('all real legal placeholder pages still satisfy the placeholder gate');

  console.log('\n──────────────────────────────────────────────────────────');
  console.log(`Passes: ${passes}  Failures: ${failures}`);
  if (failures > 0) process.exit(1);
}

main();
