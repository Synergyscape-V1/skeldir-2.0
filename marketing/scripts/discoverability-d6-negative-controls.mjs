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
import {
  validateD6EvidenceFrontLoad,
  blufOutsideMain,
  D6_FRONTLOAD_MAX_NORMALIZED,
} from './discoverability/lib/d6-evidence-frontload.mjs';
import {
  loadEntitySemanticsRegistry,
  validateD6EntitySemanticsDrift,
  validateEntitySemanticsRegistryShape,
} from './discoverability/lib/d6-entity-semantics.mjs';
import path from 'node:path';

const MARKETING_ROOT = process.cwd();

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

/** Minimal evidence-detail skeleton with configurable section order. */
function evidenceFixture({ sectionOrder, blufInMain = true }) {
  const sections = {
    bluf: `<section id="bottom-line"><h2 id="bottom-line-heading">Bottom line</h2><p>BLUF answer here.</p></section>`,
    keyFacts: `<section id="key-facts"><h2 id="key-facts-heading">Key Facts</h2><ul><li>Fact one</li></ul></section>`,
    claims: `<section id="claims-and-evidence"><h2 id="claims-evidence-heading">Claims and evidence</h2><table><tr><td>c</td><td>e</td></tr></table></section>`,
    capability: `<section><h2>Capability status</h2><p>live API unavailable on this page — not described as live.</p></section>`,
    how: `<section><h2>How Skeldir Treats This</h2><p>x</p></section>`,
    methodology: `<section id="methodology"><h2 id="methodology-heading">Methodology</h2><p>m</p></section>`,
    notProve: `<section><h2>What This Does Not Prove</h2><p>n</p></section>`,
    limitations: `<section id="limitations"><h2 id="limitations-heading">Limitations</h2><p>lim</p></section>`,
    relatedM: `<section><h2>Related methodology pages</h2><a href="/methodology">Methodology</a></section>`,
    questions: `<section><h2>Common questions</h2><a href="/resources/evidence">Q</a></section>`,
    lastReviewed: `<section><h2>Last Reviewed</h2><p>2026-05-23</p></section>`,
    owner: `<section><h2>Owner</h2><p>Skeldir</p></section>`,
  };
  const filler = '<p>' + 'padding '.repeat(2500) + '</p>';
  const ordered = sectionOrder.map((k) => sections[k] || '').join('\n');
  const article = `<article>${ordered}</article>`;
  const mainInner = blufInMain
    ? `<header><h1>Test Evidence</h1></header>${article}`
    : `<header><h1>Test Evidence</h1></header>${article}`;
  const blufOutside = blufInMain
    ? ''
    : `<section id="bottom-line"><h2>Bottom line</h2><p>outside main</p></section>`;
  return `<!DOCTYPE html><html><head><title>Test | Skeldir Evidence Library</title><meta name="description" content="Test evidence page for negative controls."/></head><body>${blufOutside}<main>${mainInner}${filler}</main><footer>footer island ${filler}</footer></body></html>`;
}

function main() {
  console.log('╔══════════════════════════════════════════════════════════╗');
  console.log('║  Skeldir D6 — Negative controls                            ║');
  console.log('╚══════════════════════════════════════════════════════════╝\n');

  console.log('\n[NC-D6-01] Buyer matrix missing version');
  expectMin('NC-D6-01', validateBuyerQueryMatrixShape({ entries: [] }), 1);

  console.log('\n[NC-D6-02] Evidence detail missing Bottom line heading');
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

  console.log('\n[NC-D6-05] BLUF after Limitations → front-load fail');
  const lateBluf = evidenceFixture({
    sectionOrder: [
      'limitations',
      'bluf',
      'keyFacts',
      'claims',
      'capability',
      'how',
      'methodology',
      'notProve',
      'relatedM',
      'questions',
      'lastReviewed',
      'owner',
    ],
  });
  const lateErrs = validateD6EvidenceFrontLoad('/resources/evidence/nc-late-bluf', lateBluf).errors;
  expectMin('NC-D6-05', lateErrs, 1);

  console.log('\n[NC-D6-06] Key Facts below footer-scale filler in <main> → fail 30% rule');
  const lateFacts = evidenceFixture({
    sectionOrder: [
      'bluf',
      'claims',
      'capability',
      'how',
      'methodology',
      'notProve',
      'limitations',
      'relatedM',
      'questions',
      'lastReviewed',
      'owner',
    ],
  }).replace('</main>', `${'<p>' + 'late-facts-pad '.repeat(3000) + '</p>'}<section id="key-facts"><h2 id="key-facts-heading">Key Facts</h2><ul><li>late</li></ul></section></main>`);
  const lateFactsErrs = validateD6EvidenceFrontLoad('/resources/evidence/nc-late-facts', lateFacts).errors;
  expectMin('NC-D6-06', lateFactsErrs, 1);

  console.log('\n[NC-D6-07] Claims table after 30% of <main>');
  const pad = '<div>' + 'z '.repeat(8000) + '</div>';
  const lateClaimsHtml = `<!DOCTYPE html><html><body><main><h1>T</h1>${pad}<section><h2 id="bottom-line-heading">Bottom line</h2><p>b</p></section><section><h2 id="key-facts-heading">Key Facts</h2><ul><li>k</li></ul></section><section><h2 id="claims-evidence-heading">Claims and evidence</h2><table><tr><td>c</td></tr></table></section></main></body></html>`;
  const lateClaimsErrs = validateD6EvidenceFrontLoad('/resources/evidence/nc-late-claims', lateClaimsHtml, {
    maxNormalized: D6_FRONTLOAD_MAX_NORMALIZED,
  }).errors;
  expectMin('NC-D6-07', lateClaimsErrs, 1);

  console.log('\n[NC-D6-08] BLUF outside <main>');
  const outside = evidenceFixture({
    sectionOrder: ['keyFacts', 'claims', 'capability', 'how', 'methodology', 'notProve', 'limitations', 'relatedM', 'questions', 'lastReviewed', 'owner'],
    blufInMain: false,
  });
  if (blufOutsideMain(outside)) pass('NC-D6-08 blufOutsideMain detector');
  else fail('NC-D6-08 expected BLUF outside main');
  const outsideErrs = validateD6EvidenceFrontLoad('/resources/evidence/nc-outside', outside).errors;
  expectMin('NC-D6-08 validator', outsideErrs, 1);

  let entityReg;
  try {
    entityReg = loadEntitySemanticsRegistry(MARKETING_ROOT);
    const shape = validateEntitySemanticsRegistryShape(entityReg);
    if (shape.length) shape.forEach((e) => fail(`entity registry shape: ${e}`));
    else pass('entity-semantics-registry.json loads for NC-D6-09+');
  } catch (e) {
    fail(e.message);
    entityReg = null;
  }

  console.log('\n[NC-D6-09] Disallowed: Skeldir is a financial product');
  if (entityReg) {
    const badProduct = `<!DOCTYPE html><html><head><title>Bad</title><meta name="description" content="x"/></head><body><main><h1>Skeldir is a financial product</h1><section><h2 id="bottom-line-heading">Bottom line</h2><p>x</p></section><section><h2 id="key-facts-heading">Key Facts</h2><ul><li>k</li></ul></section></main></body></html>`;
    expectMin(
      'NC-D6-09',
      validateD6EntitySemanticsDrift('/resources/evidence/nc-financial', badProduct, entityReg).errors,
      1,
    );
  }

  console.log('\n[NC-D6-10] Disallowed: decision intelligence for ad spend (H1)');
  if (entityReg) {
    const badDi = `<!DOCTYPE html><html><head><title>Bad</title></head><body><main><h1>decision intelligence for ad spend</h1><section><h2 id="bottom-line-heading">Bottom line</h2><p>unqualified</p></section></main></body></html>`;
    expectMin(
      'NC-D6-10',
      validateD6EntitySemanticsDrift('/resources/evidence/nc-di', badDi, entityReg).errors,
      1,
    );
  }

  console.log('\n[NC-D6-11] Disallowed: TrustEnvelope guarantees causal attribution');
  if (entityReg) {
    const badTe = `<!DOCTYPE html><html><head><title>Bad</title></head><body><main><h1>Evidence</h1><section><h2 id="bottom-line-heading">Bottom line</h2><p>TrustEnvelope guarantees causal attribution for every order.</p></section></main></body></html>`;
    expectMin(
      'NC-D6-11',
      validateD6EntitySemanticsDrift('/resources/evidence/nc-te', badTe, entityReg).errors,
      1,
    );
  }

  console.log('\n──────────────────────────────────────────────');
  console.log(`Passes: ${passes}  Failures: ${failures}`);
  if (failures) process.exit(1);
}

main();
