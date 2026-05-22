#!/usr/bin/env node

/**
 * D4 negative controls — proves validators detect corrupt or misleading structured data.
 */

import fs from 'node:fs';
import path from 'node:path';
import { extractJsonLdScriptInnerHtmls } from './discoverability/lib/d1-html-retrieval.mjs';
import { readCrawlUrlAuthority } from './discoverability/lib/d2-crawl-graph.mjs';
import {
  validateD4IndexablePage,
  parseAllJsonLdObjects,
  loadVerifiedSameAsUrls,
} from './discoverability/lib/d4-structured-data.mjs';

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

function main() {
  console.log('╔══════════════════════════════════════════════╗');
  console.log('║  Skeldir D4 — Negative control proof              ║');
  console.log('╚══════════════════════════════════════════════╝\n');

  const auth = readCrawlUrlAuthority(MARKETING_ROOT);
  const origin = auth.SITE_ORIGIN;
  const verified = [];

  const ld = (obj) =>
    `<script type="application/ld+json">${JSON.stringify(obj).replace(/</g, '\\u003c')}</script>`;

  const headBase = `<head><meta charset="utf-8"/><title>T</title><link rel="canonical" href="${origin}/" /></head>`;

  const badParseHtml = `<html>${headBase}<body><script type="application/ld+json">{ not json</script></body></html>`;
  const rawInner = extractJsonLdScriptInnerHtmls(badParseHtml)[0];
  const parseFails = [];
  try {
    JSON.parse(rawInner);
  } catch (e) {
    parseFails.push(e.message);
  }
  expectErrors('NC-D4-01 invalid JSON-LD', parseFails, 1);

  const unsafeLt = `<html>${headBase}<body><script type="application/ld+json">{"x":"<img" }</script></body></html>`;
  try {
    parseAllJsonLdObjects(unsafeLt);
    fail('NC-D4-02 raw < should throw');
  } catch {
    pass('NC-D4-02 raw < rejected in JSON-LD');
  }

  const homeMissingOrg = {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    '@id': `${origin}/#website`,
    url: `${origin}/`,
    name: 'Skeldir',
    publisher: { '@id': `${origin}/#organization` },
  };
  const homeHtml = `<html>${headBase}<body>${ld(homeMissingOrg)}</body></html>`;
  expectErrors(
    'NC-D4-03 homepage missing Organization',
    validateD4IndexablePage(MARKETING_ROOT, '/', homeHtml, verified),
    1,
  );

  const orgOk = {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    '@id': `${origin}/#organization`,
    name: 'Skeldir',
    url: `${origin}/`,
    description:
      'Skeldir is deterministic revenue-verification and attribution infrastructure that reconciles platform-reported revenue against verified commerce and payment evidence.',
  };
  const siteOk = {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    '@id': `${origin}/#website`,
    url: `${origin}/`,
    name: 'Skeldir',
    publisher: { '@id': `${origin}/#organization` },
  };
  const aria =
    'Every ad dollar traced, verified to the source— So your AI Agents and teams execute from confirmed truth.';
  const wpOk = {
    '@context': 'https://schema.org',
    '@type': 'WebPage',
    '@id': `${origin}/#webpage`,
    url: `${origin}/`,
    name: aria,
    description:
      'Skeldir reconciles platform-reported ad revenue with verified commerce and payment evidence.',
    isPartOf: { '@id': `${origin}/#website` },
    about: { '@id': `${origin}/#organization` },
  };
  const homeGood = `<html>${headBase}<body><h1 aria-label="${aria.replace(/"/g, '&quot;')}">x</h1>${ld(orgOk)}${ld(siteOk)}${ld(wpOk)}</body></html>`;
  const homeGoodErrs = validateD4IndexablePage(MARKETING_ROOT, '/', homeGood, verified);
  if (homeGoodErrs.length) {
    homeGoodErrs.forEach((e) => fail(`golden home fixture should pass: ${e}`));
  } else pass('NC-D4-04 golden home fixture passes validator');

  const orgBadSameAs = { ...orgOk, sameAs: ['https://example.com/fake-profile'] };
  const homeBadSameAs = `<html>${headBase}<body>${ld(orgBadSameAs)}${ld(siteOk)}${ld(wpOk)}</body></html>`;
  expectErrors(
    'NC-D4-05 sameAs not in registry',
    validateD4IndexablePage(MARKETING_ROOT, '/', homeBadSameAs, verified),
    1,
  );

  const bookDemoHtml = `<html><head><title>Book</title><meta name="robots" content="noindex, follow"/><link rel="canonical" href="${origin}/book-demo"/></head><body>${ld({
    '@context': 'https://schema.org',
    '@type': 'SoftwareApplication',
    name: 'Skeldir',
    url: `${origin}/book-demo`,
  })}</body></html>`;
  expectErrors(
    'NC-D4-06 SoftwareApplication on /book-demo',
    validateD4IndexablePage(MARKETING_ROOT, '/book-demo', bookDemoHtml, verified),
    1,
  );

  const articleHtml = `<html><head><title>Wrong | Skeldir</title><link rel="canonical" href="${origin}/resources/why-your-attribution-numbers-never-match"/><meta name="description" content="x"/></head><body><h1>Why Your Attribution Numbers Never Match</h1>${ld({
    '@context': 'https://schema.org',
    '@type': 'Article',
    headline: 'Wrong headline',
    description: 'ex',
    url: `${origin}/resources/why-your-attribution-numbers-never-match`,
    datePublished: '2026-01-25',
    dateModified: '2026-01-25',
    author: { '@type': 'Person', name: 'Amulya Puri' },
    publisher: { '@id': `${origin}/#organization` },
    mainEntityOfPage: {
      '@type': 'WebPage',
      '@id': `${origin}/resources/why-your-attribution-numbers-never-match#webpage`,
    },
  })}${ld({
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'Home', item: `${origin}/` },
      { '@type': 'ListItem', position: 2, name: 'Resources', item: `${origin}/resources` },
      {
        '@type': 'ListItem',
        position: 3,
        name: 'Article',
        item: `${origin}/resources/wrong-slug`,
      },
    ],
  })}</body></html>`;
  const artErrs = validateD4IndexablePage(
    MARKETING_ROOT,
    '/resources/why-your-attribution-numbers-never-match',
    articleHtml,
    verified,
  );
  if (artErrs.length < 2) {
    fail(`NC-D4-07 article headline/breadcrumb mismatch expected ≥2 errors, got ${artErrs.length}`);
  } else pass(`NC-D4-07 article parity issues detected (${artErrs.length})`);

  const pricingOfferHtml = `<html><head><title>P</title><link rel="canonical" href="${origin}/pricing"/></head><body><h1>One platform for marketing, finance, and leadership.</h1>${ld({
    '@context': 'https://schema.org',
    '@type': 'Offer',
    price: '1',
    priceCurrency: 'USD',
  })}</body></html>`;
  expectErrors(
    'NC-D4-08 Offer on /pricing',
    validateD4IndexablePage(MARKETING_ROOT, '/pricing', pricingOfferHtml, verified),
    1,
  );

  const outIndex = path.join(MARKETING_ROOT, 'out', 'index.html');
  if (fs.existsSync(outIndex)) {
    const real = fs.readFileSync(outIndex, 'utf8');
    let v;
    try {
      v = loadVerifiedSameAsUrls(MARKETING_ROOT);
    } catch (e) {
      fail(e.message);
      v = [];
    }
    const realErrs = validateD4IndexablePage(MARKETING_ROOT, '/', real, v);
    if (realErrs.length) realErrs.forEach((e) => fail(`built index.html D4 regression: ${e}`));
    else pass('golden built index.html still passes D4 validators');
  } else {
    pass('golden built index.html skipped (run discoverability:d4 for full build)');
  }

  console.log('\n──────────────────────────────────────────────');
  console.log(`Passes: ${passes}  Failures: ${failures}`);
  if (failures > 0) process.exit(1);
}

main();
