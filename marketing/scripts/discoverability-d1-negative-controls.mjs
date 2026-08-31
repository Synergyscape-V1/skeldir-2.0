#!/usr/bin/env node

/**
 * D1 negative controls — proves validators detect violations (non-vacuous harness).
 */

import {
  validateArticleHtml,
  validateMarketingCommercialHtml,
  validateResourcesHubAnchors,
  validateNoUseClientOnArticleDocument,
  validateArticleJsonLdAgainstMetadata,
  validateRegistryArticleInstances,
  validateBookDemoSitemapContainment,
} from './discoverability/lib/d1-html-retrieval.mjs';

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
    pass(`${label} → detected ${errs.length} issue(s): ${errs[0]}`);
    return true;
  }
  fail(`${label} → expected ≥${min} error(s), got ${errs?.length ?? 0}`);
  return false;
}

function expectClean(label, errs) {
  if (!errs || errs.length === 0) {
    pass(`${label} → no false positives`);
    return true;
  }
  fail(`${label} → unexpected errors: ${errs.join('; ')}`);
  return false;
}

function main() {
  console.log('╔══════════════════════════════════════════════╗');
  console.log('║  Skeldir D1 — Negative control proof          ║');
  console.log('╚══════════════════════════════════════════════╝\n');

  const shell = `<!DOCTYPE html><html><body><div class="min-h-screen flex items-center justify-center bg-white">
    <div class="animate-pulse text-gray-400">Loading...</div></body></html>`;
  expectErrors('NC-1 loading shell article', validateArticleHtml(shell));

  const noH1 = `<!DOCTYPE html><html><body><h2>x</h2><h2>y</h2><h2>z</h2><p>${'word '.repeat(300)}</p>
    <time>January 2026</time><p>By Author Name</p><script type="application/ld+json">{"@type":"Article"}</script></body></html>`;
  expectErrors('NC-2 missing h1', validateArticleHtml(noH1));

  const shortBody = `<!DOCTYPE html><html><body><h1>Title</h1><h2>a</h2><h2>b</h2><h2>c</h2><p>short</p>
    <p>By Someone</p><time>2026-01-01</time><script type="application/ld+json">{}</script></body></html>`;
  expectErrors('NC-3 insufficient body text', validateArticleHtml(shortBody));

  const fewHeadings = `<!DOCTYPE html><html><body><h1>T</h1><h2>only one</h2><p>${'x '.repeat(600)}</p>
    <p>By X</p><span>January 2026</span><script type="application/ld+json">{}</script></body></html>`;
  expectErrors('NC-4 too few h2/h3', validateArticleHtml(fewHeadings));

  const hubBad = `<html><body><a href="/resources/why-your-attribution-numbers-never-match">ok</a></body></html>`;
  expectErrors(
    'NC-5 resources hub missing slugs',
    validateResourcesHubAnchors(hubBad, [
      'why-your-attribution-numbers-never-match',
      'roas-is-not-a-number-its-a-range',
      'attribution-methods-answer-different-questions',
      'confidently-defend-budget-shift',
    ]),
    1
  );

  const commercialShell = `<html><body><div class="animate-pulse">Loading...</div></body></html>`;
  expectErrors('NC-6 commercial loading shell', validateMarketingCommercialHtml(commercialShell));

  console.log('\n[NC-7] use client scan must not false-positive on clean tree');
  const marketingRoot = process.cwd();
  const uc = validateNoUseClientOnArticleDocument(marketingRoot);
  expectClean('NC-7 clean article document files', uc);

  console.log('\n[NC-8] JSON-LD invalid JSON');
  const badJsonLd = `<!DOCTYPE html><html><body><h1>T</h1><h2>a</h2><h2>b</h2><h2>c</h2><p>${'x '.repeat(600)}</p><p>By X</p><span>January 2026</span><script type="application/ld+json">{ not json </script></body></html>`;
  expectErrors('NC-8 JSON-LD parse', validateArticleJsonLdAgainstMetadata(badJsonLd, { slug: 'x', title: 'T', excerpt: 'e', publishDate: '2026-01-01' }), 1);

  console.log('\n[NC-9] JSON-LD headline mismatch');
  const meta = { slug: 'why-your-attribution-numbers-never-match', title: 'Correct Title', excerpt: 'e', publishDate: '2026-01-01', author: 'A' };
  const mismatchLd = `<html><body><script type="application/ld+json">${JSON.stringify({
    '@context': 'https://schema.org',
    '@type': 'Article',
    headline: 'Wrong Title',
    description: 'e',
    datePublished: '2026-01-01',
    author: { '@type': 'Organization', name: 'A' },
    mainEntityOfPage: { '@type': 'WebPage', '@id': 'https://skeldir.com/resources/why-your-attribution-numbers-never-match' },
    url: 'https://skeldir.com/resources/why-your-attribution-numbers-never-match',
  })}</script></body></html>`;
  expectErrors('NC-9 headline mismatch', validateArticleJsonLdAgainstMetadata(mismatchLd, meta), 1);

  console.log('\n[NC-10] registry article instance missing slugs');
  const fakeRegistry = { routes: [{ route_type: 'article', generated_concrete_routes: ['/resources/why-your-attribution-numbers-never-match'] }] };
  expectErrors(
    'NC-10 incomplete registry',
    validateRegistryArticleInstances(fakeRegistry, [
      'why-your-attribution-numbers-never-match',
      'roas-is-not-a-number-its-a-range',
      'attribution-methods-answer-different-questions',
      'confidently-defend-budget-shift',
    ]),
    1
  );

  console.log('\n[NC-11] /book-demo illegal sitemap_required');
  const badBook = {
    routes: [
      {
        id: 'route-book-demo',
        logical_route: '/book-demo',
        sitemap_required: true,
        sitemap_implemented: false,
        status: 'active_defective_until_static_body_verified',
      },
    ],
  };
  expectErrors('NC-11 book-demo sitemap_required', validateBookDemoSitemapContainment(badBook), 1);

  console.log('\n──────────────────────────────────────────────');
  console.log(`Passes: ${passes}  Failures: ${failures}`);
  if (failures > 0) process.exit(1);
}

main();
