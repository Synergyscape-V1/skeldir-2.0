#!/usr/bin/env node

/**
 * D6 negative controls — prove validators fire on broken fixtures.
 */

import {
  validateBuyerQueryMatrixShape,
  validateD6EvidenceDetailHtml,
  validateD6EvidenceHubHtml,
  jaccardWordSimilarity,
} from './discoverability/lib/d6-evidence-library.mjs';

let failures = 0;
let passes = 0;

function fail(m) {
  console.error(`  ❌ FAIL: ${m}`);
  failures++;
}
function pass(m) {
  console.log(`  ✅ PASS: ${m}`);
  passes++;
}

function expectMin(label, errs, n) {
  if (errs.length >= n) pass(`${label} (${errs.length} issues)`);
  else {
    fail(`${label}: expected ≥${n} errors, got ${errs.length}`);
  }
}

function main() {
  console.log('╔══════════════════════════════════════════════════════════╗');
  console.log('║  Skeldir D6 — Negative controls                            ║');
  console.log('╚══════════════════════════════════════════════════════════╝\n');

  console.log('\n[NC-D6-01] Buyer matrix missing version');
  expectMin('NC-D6-01', validateBuyerQueryMatrixShape({ entries: [] }), 1);

  console.log('\n[NC-D6-02] Evidence detail missing BLUF heading');
  const badDetail =
    '<html><head><title>x</title></head><body><h1>Test</h1><p>word '.repeat(400) + '</p></body></html>';
  expectMin('NC-D6-02', validateD6EvidenceDetailHtml('', '/resources/evidence/x', badDetail), 1);

  console.log('\n[NC-D6-03] Evidence hub missing cluster marker');
  const badHub = '<html><head><title>x</title></head><body><h1>Evidence Library</h1><p>short</p></body></html>';
  expectMin('NC-D6-03', validateD6EvidenceHubHtml('', badHub), 1);

  console.log('\n[NC-D6-04] Identical spam pages → Jaccard ~1');
  const spam = 'foo bar baz ' + 'x '.repeat(200);
  const sim = jaccardWordSimilarity(spam, spam);
  if (sim >= 0.99) pass(`NC-D6-04 identical text similarity ${sim.toFixed(3)}`);
  else fail('NC-D6-04 expected near-1 similarity');

  console.log('\n──────────────────────────────────────────────');
  console.log(`Passes: ${passes}  Failures: ${failures}`);
  if (failures) process.exit(1);
}

main();
