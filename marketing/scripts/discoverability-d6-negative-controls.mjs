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
import { validateD6MethodologyExposure } from './discoverability/lib/d6-methodology-exposure.mjs';
import { validateD6TrustEnvelopeExposure } from './discoverability/lib/d6-trust-envelope-exposure.mjs';
import { validateD6RevenueVerificationExposure } from './discoverability/lib/d6-revenue-verification-exposure.mjs';
import { validateD6AttributionMethodologyExposure } from './discoverability/lib/d6-attribution-methodology-exposure.mjs';
import { validateD6DiscrepancyTaxonomyExposure } from './discoverability/lib/d6-discrepancy-taxonomy-exposure.mjs';
import { validateD6AiBoundaryExposure } from './discoverability/lib/d6-ai-boundary-exposure.mjs';
import { validateD6SecurityExposure } from './discoverability/lib/d6-security-exposure.mjs';
import { validateD6StatusExposure } from './discoverability/lib/d6-status-exposure.mjs';
import { validateD6PressExposure } from './discoverability/lib/d6-press-exposure.mjs';
import { validateD6CareersExposure } from './discoverability/lib/d6-careers-exposure.mjs';
import { validateD6ApiExposure } from './discoverability/lib/d6-api-exposure.mjs';
import { validateD6PrivacyExposure } from './discoverability/lib/d6-privacy-exposure.mjs';
import { validateD6AboutExposure } from './discoverability/lib/d6-about-exposure.mjs';
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

  console.log('\n[NC-D6-12] /methodology must fail on internal status token in HTML');
  const badMethodology =
    '<!DOCTYPE html><html><head><title>M</title></head><body><main><h1>How Skeldir Produces Verified Revenue Truth</h1><code>technical_disclosure_only</code><h2>Bottom Line Up Front</h2><p>x</p><h2>Five things that are true about this methodology</h2><ul><li>a</li></ul><h2>How deterministic reconciliation works</h2><p>d</p><h2>What counts as verified evidence</h2><p>v</p><h2>What attribution models prove</h2><p>a</p><h2>How discrepancies are classified</h2><p>c</p><h2>How delayed evidence is handled</h2><p>l</p><h2>How confidence is expressed</h2><p>f</p><h2>Why LLMs do not compute financial truth</h2><p>i</p><h2>Limitations</h2><p>l</p><p>Last updated: February 2026</p><a href="/revenue-verification">r</a><a href="/attribution-methodology">a</a><a href="/discrepancy-taxonomy">d</a><a href="/ai-boundary">b</a></main></body></html>';
  expectMin('NC-D6-12', validateD6MethodologyExposure(badMethodology), 1);

  console.log('\n[NC-D6-13] /methodology must fail on match kernel leakage');
  const leakyMethodology = badMethodology.replace(
    'technical_disclosure_only',
    'Last updated February 2026 technical disclosure not a contract',
  ).replace('<h2>How deterministic reconciliation works</h2>', '<h2>How deterministic reconciliation works</h2><p>match kernel logic</p>');
  expectMin('NC-D6-13', validateD6MethodologyExposure(leakyMethodology), 1);

  console.log('\n[NC-D6-14] /trust-envelope must fail on serialized envelope leakage');
  const badTe =
    '<!DOCTYPE html><html><head><title>TE</title></head><body><main><h1>TrustEnvelope</h1><p>serialized envelope</p><h2>Key facts</h2><ul><li>a</li></ul><h2>What is a TrustEnvelope</h2><p>x</p><h2>Deterministic values</h2><p>d</p><h2>provenance chain</h2><p>p</p><h2>semantic truth hash</h2><p>s</p><h2>artifact hash</h2><p>a</p><h2>Confidence status</h2><p>c</p><h2>Benchmark metadata</h2><p>b</p><h2>Policy authority</h2><p>pa</p><h2>Fallback reason</h2><p>f</p><h2>External verification metadata</h2><p>e</p><h2>Action authority</h2><p>aa</p><h2>Audit trail</h2><p>at</p><h2>Limitations</h2><p>l</p><p>Last updated: February 2026</p><p>does not promise a live public API</p><p>documented separately</p><a href="/methodology">m</a><a href="/revenue-verification">r</a><a href="/attribution-methodology">a</a><a href="/discrepancy-taxonomy">d</a><a href="/ai-boundary">b</a><a href="/api">api</a><a href="/docs">docs</a></main></body></html>';
  expectMin('NC-D6-14', validateD6TrustEnvelopeExposure(badTe), 1);

  console.log('\n[NC-D6-15] /trust-envelope must fail on technical_disclosure_only token');
  const badTeToken = badTe.replace('serialized envelope', 'x').replace(
    '<h1>TrustEnvelope</h1>',
    '<h1>TrustEnvelope</h1><code>technical_disclosure_only</code>',
  );
  expectMin('NC-D6-15', validateD6TrustEnvelopeExposure(badTeToken), 1);

  console.log('\n[NC-D6-16] /revenue-verification must fail on three joined streams');
  const badRv =
    '<!DOCTYPE html><html><head><title>RV</title></head><body><main><h1>Revenue Verification</h1><p>three joined streams</p><h2>Key facts</h2><ul><li>a</li></ul><h2>Why platform-reported revenue</h2><p>x</p><h2>Commerce evidence</h2><p>c</p><h2>Payment evidence</h2><p>p</p><h2>How Skeldir verifies revenue</h2><p>v</p><h2>How discrepancies are handled</h2><p>d</p><h2>Delayed evidence</h2><p>l</p><h2>What revenue verification proves</h2><p>pr</p><h2>What revenue verification does not prove</h2><p>np</p><h2>Limitations</h2><p>Operational limitations</p><p>Last updated: February 2026</p><p>informational does not replace contractual terms</p><a href="/methodology">m</a><a href="/discrepancy-taxonomy">d</a><a href="/attribution-methodology">a</a><a href="/ai-boundary">b</a><a href="/trust-envelope">t</a></main></body></html>';
  expectMin('NC-D6-16', validateD6RevenueVerificationExposure(badRv), 1);

  console.log('\n[NC-D6-17] /revenue-verification must fail on customer identifiers');
  const badRvPii = badRv
    .replace('three joined streams', 'x')
    .replace('<h2>Commerce evidence</h2><p>c</p>', '<h2>Commerce evidence</h2><p>customer identifiers</p>');
  expectMin('NC-D6-17', validateD6RevenueVerificationExposure(badRvPii), 1);

  console.log('\n[NC-D6-18] /attribution-methodology must fail on reproduce the model output');
  const badAm =
    '<!DOCTYPE html><html><head><title>AM</title></head><body><main><h1>Attribution Methodology</h1><p>reproduce the model output</p><h2>Key facts</h2><ul><li>a</li></ul><h2>What attribution models answer</h2><p>x</p><h2>What assumptions mean</h2><p>a</p><h2>Why attribution models are bounded</h2><p>b</p><h2>Why attribution is not causality</h2><p>c</p><h2>How attribution output relates to deterministic revenue</h2><p>verified revenue deterministic model-derived distributes credit causal lift controlled experimentation incrementality</p><h2>Limitations</h2><p>Current limitations</p><p>Last updated: February 2026</p><p>confused with verified revenue causal lift informational does not replace contractual terms</p><a href="/methodology">m</a><a href="/revenue-verification">r</a><a href="/discrepancy-taxonomy">d</a><a href="/ai-boundary">b</a><a href="/trust-envelope">t</a></main></body></html>';
  expectMin('NC-D6-18', validateD6AttributionMethodologyExposure(badAm), 1);

  console.log('\n[NC-D6-19] /attribution-methodology must fail on first-touch model catalog');
  const badAmCatalog = badAm
    .replace('reproduce the model output', 'x')
    .replace('<h2>What assumptions mean</h2><p>a</p>', '<h2>What assumptions mean</h2><p>first-touch</p>');
  expectMin('NC-D6-19', validateD6AttributionMethodologyExposure(badAmCatalog), 1);

  console.log('\n[NC-D6-20] /discrepancy-taxonomy must fail on defined evidence signature');
  const badDt =
    '<!DOCTYPE html><html><head><title>DT</title></head><body><main><h1>Discrepancy Taxonomy</h1><p>defined evidence signature</p><h2>Key facts</h2><ul><li>a</li></ul><h2>Timing mismatch</h2><p>timing mismatch</p><h2>Currency, tax, or shipping mismatch</h2><p>currency tax shipping</p><h2>Refund and chargeback adjustment</h2><p>refund chargeback</p><h2>Attribution-window mismatch</h2><p>attribution-window</p><h2>Duplicate or order-reference mismatch</h2><p>duplicate</p><h2>Missing commerce evidence</h2><p>missing commerce</p><h2>Unmatched platform claim</h2><p>unmatched platform</p><h2>Delayed arrival</h2><p>delayed arrival</p><h2>Limitations</h2><p>Current limitations classified by type informational does not replace contractual terms does not erase, average, or guess</p><p>Last updated: February 2026</p><a href="/methodology">m</a><a href="/revenue-verification">r</a><a href="/attribution-methodology">a</a><a href="/ai-boundary">b</a><a href="/trust-envelope">t</a></main></body></html>';
  expectMin('NC-D6-20', validateD6DiscrepancyTaxonomyExposure(badDt), 1);

  console.log('\n[NC-D6-21] /discrepancy-taxonomy must fail on deduplicates against');
  const badDtDedup = badDt
    .replace('defined evidence signature', 'x')
    .replace('<h2>Duplicate or order-reference mismatch</h2><p>duplicate</p>', '<h2>Duplicate or order-reference mismatch</h2><p>deduplicates against commerce identifier</p>');
  expectMin('NC-D6-21', validateD6DiscrepancyTaxonomyExposure(badDtDedup), 1);

  console.log('\n[NC-D6-22] /ai-boundary must fail on semantic truth hash');
  const badAi =
    '<!DOCTYPE html><html><head><title>AI</title></head><body><main><h1>AI Boundary</h1><h2>Bottom Line Up Front</h2><p>deterministic authoritative advisory does not calculate financial truth TrustEnvelope verification status LLM explain</p><h2>Key facts</h2><ul><li>a</li></ul><h2>What LLMs do in Skeldir</h2><p>x</p><h2>Why LLMs do not compute financial truth</h2><p>y</p><h2>Deterministic grounding</h2><p>g</p><h2>Bounded explanations</h2><p>b</p><h2>Policy for AI agents consuming Skeldir</h2><p>agent policy approval</p><h2>Scope and trust boundary</h2><p>s</p><h2>Limitations</h2><p>Current limitations</p><p>Last updated: February 2026</p><p>public AI boundary documented separately</p><a href="/methodology">m</a><a href="/trust-envelope">t</a><a href="/revenue-verification">r</a><a href="/attribution-methodology">a</a><a href="/discrepancy-taxonomy">d</a><a href="/api">api</a><a href="/docs">docs</a></main></body></html>';
  const badAiHash = badAi.replace(
    '<h2>Deterministic grounding</h2><p>g</p>',
    '<h2>Deterministic grounding</h2><p>semantic truth hash</p>',
  );
  expectMin('NC-D6-22', validateD6AiBoundaryExposure(badAiHash), 1);

  console.log('\n[NC-D6-23] /ai-boundary must fail on Design Partner Mode');
  const badAiDpm = badAi.replace(
    '<h2>Policy for AI agents consuming Skeldir</h2><p>agent policy approval</p>',
    '<h2>Policy for AI agents consuming Skeldir</h2><p>Design Partner Mode simulation_only</p>',
  );
  expectMin('NC-D6-23', validateD6AiBoundaryExposure(badAiDpm), 1);

  console.log('\n[NC-D6-24] /security must fail on row-level security');
  const badSec =
    '<!DOCTYPE html><html><head><title>SEC</title></head><body><main><h1>Security</h1><h2>Key facts</h2><ul><li>a</li></ul><h2>Security posture principles</h2><p>tenant security posture privacy audit vulnerability</p><h2>Tenant isolation</h2><p>t</p><h2>Sensitive data handling</h2><p>s</p><h2>Financial value precision</h2><p>f</p><h2>Auditability</h2><p>a</p><h2>Security inquiries</h2><p>security documentation procurement vulnerability security@skeldir.com controlled direct security engagement</p><h2>Limitations</h2><p>Current limitations public security posture direct security engagement controlled</p><p>Last updated: February 2026</p><a href="/methodology">m</a><a href="/revenue-verification">r</a><a href="/trust-envelope">t</a><a href="/ai-boundary">b</a><a href="/privacy">p</a><a href="/api">api</a><a href="/docs">docs</a></main></body></html>';
  const badSecRls = badSec.replace(
    '<h2>Tenant isolation</h2><p>t</p>',
    '<h2>Tenant isolation</h2><p>row-level security</p>',
  );
  expectMin('NC-D6-24', validateD6SecurityExposure(badSecRls), 1);

  console.log('\n[NC-D6-25] /security must fail on SOC 2 certified overclaim');
  const badSecSoc = badSec.replace(
    '<h2>Security posture principles</h2><p>tenant',
    '<h2>Security posture principles</h2><p>SOC 2 certified tenant',
  );
  expectMin('NC-D6-25', validateD6SecurityExposure(badSecSoc), 1);

  console.log('\n[NC-D6-26] /status must fail on placeholder');
  const badSt =
    '<!DOCTYPE html><html><head><title>ST</title></head><body><main><h1>Status</h1><p>placeholder</p><h2>Key facts</h2><ul><li>a</li></ul><h2>Current status</h2><p>c</p><h2>Active incidents</h2><p>no active incidents</p><h2>Scheduled maintenance</h2><p>no scheduled maintenance</p><h2>Communication</h2><p>manually verified not an automated real-time</p><h2>Scope</h2><p>s</p><h2>Report an issue</h2><p>support@skeldir.com</p><p>Last updated: February 2026</p><a href="/security">sec</a><a href="/privacy">p</a><a href="/methodology">m</a><a href="/trust-envelope">t</a><a href="/docs">d</a></main></body></html>';
  expectMin('NC-D6-26', validateD6StatusExposure(badSt, { active_incidents: [], scheduled_maintenance: [], operator_contact_channel: 'support@skeldir.com', indexability: true }), 1);

  console.log('\n[NC-D6-27] /status must fail on fully operational overclaim');
  const badStOp = badSt
    .replace('placeholder', 'x')
    .replace('<h2>Current status</h2><p>c</p>', '<h2>Current status</h2><p>fully operational</p>');
  expectMin('NC-D6-27', validateD6StatusExposure(badStOp, { active_incidents: [], scheduled_maintenance: [], operator_contact_channel: 'support@skeldir.com', indexability: true }), 1);

  console.log('\n[NC-D6-28] /press must fail on placeholder');
  const badPr =
    '<!DOCTYPE html><html><head><title>PR</title></head><body><main><h1>Press</h1><h2>Bottom Line Up Front</h2><p>x</p><h2>Key facts</h2><ul><li>a</li></ul><h2>Technical disclosures</h2><p>published methodology unpublished capabilities unannounced integrations revenue projections roadmap</p><h2>Inquiry routing</h2><p>i</p><h2>Scope of public information</h2><p>internal architecture, implementation modules, phase identifiers, schema details, and pipeline specifics are not disclosed publicly</p><h2>Contact</h2><p>press@skeldir.com</p><p>Last updated: February 2026</p><a href="/methodology">m</a><a href="/revenue-verification">r</a><a href="/attribution-methodology">a</a><a href="/discrepancy-taxonomy">d</a><a href="/trust-envelope">t</a><a href="/ai-boundary">b</a><a href="/security">s</a><a href="/status">st</a></main></body></html>';
  expectMin(
    'NC-D6-28',
    validateD6PressExposure(
      badPr.replace('<h2>Bottom Line Up Front</h2><p>x</p>', '<h2>Bottom Line Up Front</h2><p>placeholder</p>'),
      { contacts: [{ email: 'press@skeldir.com', publicly_rendered: true }] },
      { indexability: true, sitemap_required: true, approved_media_claims: [] },
    ),
    1,
  );

  console.log('\n[NC-D6-29] /press must fail on TrustEnvelope contracts leakage');
  const badPrLeak = badPr.replace(
    '<h2>Technical disclosures</h2><p>published',
    '<h2>Technical disclosures</h2><p>TrustEnvelope contracts published',
  );
  expectMin(
    'NC-D6-29',
    validateD6PressExposure(
      badPrLeak,
      { contacts: [{ email: 'press@skeldir.com', publicly_rendered: true }] },
      { indexability: true, sitemap_required: true, approved_media_claims: [] },
    ),
    1,
  );

  console.log('\n[NC-D6-30] /careers must fail on placeholder');
  const badCar =
    '<!DOCTYPE html><html><head><title>CAR</title></head><body><main><h1>Careers</h1><h2>Bottom Line Up Front</h2><p>not a job board no public roles not an exhaustive list</p><h2>Key facts</h2><ul><li>a</li></ul><h2>What We Value</h2><p>v</p><h2>How We Hire</h2><p>h</p><h2>How to Express Interest</h2><p>i</p><h2>Scope and Trust Boundary</h2><p>s</p><h2>Contact</h2><p>engineering@skeldir.com</p><p>Last updated: February 2026</p></main></body></html>';
  expectMin(
    'NC-D6-30',
    validateD6CareersExposure(
      badCar.replace('<h2>Bottom Line Up Front</h2><p>', '<h2>Bottom Line Up Front</h2><p>placeholder '),
      { active_roles_count: 0, talent_contact_channel: 'engineering@skeldir.com', contact_approved: true, job_posting_allowed: false, approved_benefit_claims: [] },
      { contacts: [{ email: 'engineering@skeldir.com', publicly_rendered: true, contact_type: 'careers' }] },
    ),
    1,
  );

  console.log('\n[NC-D6-31] /careers must fail on row-level security leakage');
  const badCarRls = badCar.replace('<h2>What We Value</h2><p>v</p>', '<h2>What We Value</h2><p>row-level security</p>');
  expectMin(
    'NC-D6-31',
    validateD6CareersExposure(
      badCarRls,
      { active_roles_count: 0, talent_contact_channel: 'engineering@skeldir.com', contact_approved: true, job_posting_allowed: false, approved_benefit_claims: [] },
      { contacts: [{ email: 'engineering@skeldir.com', publicly_rendered: true }] },
    ),
    1,
  );

  console.log('\n[NC-D6-32] /api must fail on OpenAPI leakage');
  const badApi =
    '<!DOCTYPE html><html><head><title>API</title></head><body><main><h1>API</h1><h2>Bottom Line Up Front</h2><p>authorized integrator agreement concrete endpoint authentication details verification context deterministic value verification status advisory</p><h2>Key facts</h2><ul><li>a</li></ul><h2>What API access represents</h2><p>x</p><h2>What context accompanies programmatic output</h2><p>c</p><h2>How agents consume Skeldir output responsibly</h2><p>g</p><h2>How access is governed</h2><p>v</p><h2>Current operational boundaries</h2><p>b sales@skeldir.com</p><p>Last updated: February 2026</p><a href="/trust-envelope">t</a><a href="/methodology">m</a><a href="/revenue-verification">r</a><a href="/ai-boundary">b</a><a href="/security">s</a><a href="/docs">d</a><a href="/privacy">p</a></main></body></html>';
  expectMin(
    'NC-D6-32',
    validateD6ApiExposure(
      badApi.replace('<h2>What API access represents</h2><p>x</p>', '<h2>What API access represents</h2><p>OpenAPI</p>'),
      {
        public_api_reference_available: false,
        public_endpoint_details_rendered: false,
        contact_channel: 'sales@skeldir.com',
        contact_approved: true,
        indexability: true,
        sitemap_required: true,
        required_boundary_phrases: ['authorized integrator', 'agreement', 'concrete endpoint', 'authentication details', 'verification context', 'deterministic value', 'verification status', 'advisory'],
      },
      { contacts: [{ email: 'sales@skeldir.com', publicly_rendered: true, contact_type: 'sales' }] },
    ),
    1,
  );

  console.log('\n[NC-D6-33] /api must fail on semantic truth hash leakage');
  const badApiHash = badApi.replace('<h2>What context accompanies programmatic output</h2><p>c</p>', '<h2>What context accompanies programmatic output</h2><p>semantic truth hash</p>');
  expectMin(
    'NC-D6-33',
    validateD6ApiExposure(
      badApiHash,
      {
        public_api_reference_available: false,
        public_endpoint_details_rendered: false,
        contact_channel: 'sales@skeldir.com',
        contact_approved: true,
        indexability: true,
        sitemap_required: true,
        required_boundary_phrases: ['authorized integrator', 'agreement', 'concrete endpoint', 'authentication details', 'verification context', 'deterministic value', 'verification status', 'advisory'],
      },
      { contacts: [{ email: 'sales@skeldir.com', publicly_rendered: true }] },
    ),
    1,
  );

  console.log('\n[NC-D6-34] /privacy must fail on HMAC leakage');
  const badPriv =
    '<!DOCTYPE html><html><head><title>Privacy</title><meta name="robots" content="noindex,follow"></head><body><main><h1>Privacy</h1><h2>Bottom Line Up Front</h2><p>public privacy posture privacy posture summary not a complete legal privacy policy data minimization tenant-scoped approved legal and operator channels</p><h2>Key facts</h2><ul><li>a</li></ul><h2>Privacy posture</h2><p>x</p><h2>Data Skeldir processes</h2><p>d</p><h2>Data minimization</h2><p>m</p><h2>Tenant-scoped data handling</h2><p>t</p><h2>Legal and operator documentation boundary</h2><p>l</p><h2>Contact</h2><p>engineering@skeldir.com security@skeldir.com</p><p>Last updated: February 2026</p><a href="/security">s</a><a href="/methodology">m</a><a href="/revenue-verification">r</a><a href="/trust-envelope">t</a><a href="/ai-boundary">b</a><a href="/gdpr">g</a></main></body></html>';
  expectMin(
    'NC-D6-34',
    validateD6PrivacyExposure(
      badPriv.replace('<h2>Data Skeldir processes</h2><p>d</p>', '<h2>Data Skeldir processes</h2><p>HMAC</p>'),
      {
        public_page_type: 'privacy_posture',
        legal_review_status: 'pending',
        indexability: false,
        sitemap_required: false,
        contact_channels: ['engineering@skeldir.com', 'security@skeldir.com'],
        contact_approved: true,
        required_boundary_phrases: [
          'public privacy posture',
          'privacy posture summary',
          'not a complete legal privacy policy',
          'data minimization',
          'tenant-scoped',
          'approved legal and operator channels',
        ],
      },
      {
        contacts: [
          { email: 'engineering@skeldir.com', publicly_rendered: true },
          { email: 'security@skeldir.com', publicly_rendered: true },
        ],
      },
    ),
    1,
  );

  console.log('\n[NC-D6-35] /privacy must fail on GDPR compliant overclaim');
  expectMin(
    'NC-D6-35',
    validateD6PrivacyExposure(
      badPriv.replace('<h2>Privacy posture</h2><p>x</p>', '<h2>Privacy posture</h2><p>GDPR compliant</p>'),
      {
        public_page_type: 'privacy_posture',
        legal_review_status: 'pending',
        indexability: false,
        sitemap_required: false,
        contact_channels: ['engineering@skeldir.com', 'security@skeldir.com'],
        contact_approved: true,
        required_boundary_phrases: [
          'public privacy posture',
          'privacy posture summary',
          'not a complete legal privacy policy',
          'data minimization',
          'tenant-scoped',
          'approved legal and operator channels',
        ],
      },
      {
        contacts: [
          { email: 'engineering@skeldir.com', publicly_rendered: true },
          { email: 'security@skeldir.com', publicly_rendered: true },
        ],
      },
    ),
    1,
  );

  console.log('\n[NC-D6-36] /about must fail on integer-cents reconciliation leakage');
  const badAbout =
    '<!DOCTYPE html><html><head><title>About</title></head><body><main><h1>About Skeldir</h1><h2>Bottom Line Up Front</h2><p>financial-trust infrastructure deterministic revenue verification platform-reported independent commerce not an analytics dashboard not an AI attribution assistant verification scope</p><h2>Key facts</h2><ul><li>financial-trust infrastructure deterministic revenue verification verified revenue independent commerce and payment evidence audit-ready trust context privacy-preserving design tenant-scoped financial memory AI explanation boundary</li></ul><h2>What Skeldir Does</h2><p>x</p><h2>Principles That Govern Skeldir</h2><p>p</p><h2>Who Skeldir Serves</h2><p>w</p><h2>How Skeldir Differs From Analytics and Attribution Platforms</h2><p>d</p><h2>How Organizations Engage With Skeldir</h2><p>e</p><p>Last updated: February 2026</p><a href="/methodology">m</a><a href="/revenue-verification">r</a><a href="/attribution-methodology">a</a><a href="/discrepancy-taxonomy">d</a><a href="/trust-envelope">t</a><a href="/ai-boundary">b</a><a href="/security">s</a><a href="/privacy">p</a><a href="/api">i</a><a href="/docs">o</a></main></body></html>';
  expectMin(
    'NC-D6-36',
    validateD6AboutExposure(
      badAbout.replace('<h2>What Skeldir Does</h2><p>x</p>', '<h2>What Skeldir Does</h2><p>integer-cents reconciliation</p>'),
      {
        indexability: true,
        sitemap_required: true,
        canonical_entity_definition: 'financial-trust infrastructure deterministic revenue verification',
        required_boundary_phrases: [
          'financial-trust infrastructure',
          'deterministic revenue verification',
          'platform-reported',
          'independent commerce',
          'not an analytics dashboard',
          'not an AI attribution assistant',
          'verification scope',
        ],
        approved_positioning_terms: [
          'financial-trust infrastructure',
          'deterministic revenue verification',
          'verified revenue',
          'independent commerce and payment evidence',
          'audit-ready trust context',
          'privacy-preserving design',
          'tenant-scoped financial memory',
          'AI explanation boundary',
        ],
      },
      {},
    ),
    1,
  );

  console.log('\n[NC-D6-37] /about must fail on primary analytics dashboard positioning');
  expectMin(
    'NC-D6-37',
    validateD6AboutExposure(
      badAbout.replace(
        '<h2>Bottom Line Up Front</h2><p>financial-trust',
        '<h2>Bottom Line Up Front</h2><p>Skeldir is an analytics dashboard. financial-trust',
      ),
      {
        indexability: true,
        sitemap_required: true,
        required_boundary_phrases: [
          'financial-trust infrastructure',
          'deterministic revenue verification',
          'platform-reported',
          'independent commerce',
          'not an analytics dashboard',
          'not an AI attribution assistant',
          'verification scope',
        ],
        approved_positioning_terms: [
          'financial-trust infrastructure',
          'deterministic revenue verification',
          'verified revenue',
          'independent commerce and payment evidence',
          'audit-ready trust context',
          'privacy-preserving design',
          'tenant-scoped financial memory',
          'AI explanation boundary',
        ],
      },
      {},
    ),
    1,
  );

  console.log('\n──────────────────────────────────────────────');
  console.log(`Passes: ${passes}  Failures: ${failures}`);
  if (failures) process.exit(1);
}

main();
