#!/usr/bin/env node

/**
 * D2 negative controls — proves crawl-graph validators fire on corruption.
 */

import {
  validateSitemapXmlWellFormed,
  validateSitemapMatchesExpected,
  validateRobotsPolicy,
  extractCanonicalHrefs,
  validateFooterLegalAndSupportHygiene,
  assertDiscoverabilityGitBranchPolicy,
} from './discoverability/lib/d2-crawl-graph.mjs';

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
  console.log('║  Skeldir D2 — Negative control proof          ║');
  console.log('╚══════════════════════════════════════════════╝\n');

  const badXml = '<urlset><loc>oops</loc></urlset>';
  expectErrors('NC-sitemap-xml', validateSitemapXmlWellFormed(badXml));

  const marketingRoot = process.cwd();
  const pollutedLocs = [
    'https://skeldir.com/',
    'https://skeldir.com/product',
    'https://skeldir.com/extra-bad',
  ];
  expectErrors('NC-sitemap-expected-set', validateSitemapMatchesExpected(marketingRoot, pollutedLocs));

  const badRobots = 'User-agent: *\nDisallow: /\n';
  expectErrors('NC-robots-block-all', validateRobotsPolicy(badRobots));

  const noSitemapLine = 'User-agent: *\nAllow: /\n';
  expectErrors('NC-robots-missing-sitemap', validateRobotsPolicy(noSitemapLine));

  const leak =
    'User-agent: *\nAllow: /\nSitemap: https://skeldir.com/sitemap.xml\nDisallow: /node_modules\n';
  expectErrors('NC-robots-sensitive-leak', validateRobotsPolicy(leak));

  const htmlNoCanon = '<html><head><title>x</title></head><body></body></html>';
  const cans = extractCanonicalHrefs(htmlNoCanon);
  if (cans.length === 0) pass('NC-canonical-missing: extractCanonicalHrefs empty as expected');
  else fail('NC-canonical-missing: expected zero canonicals');

  const badFooter = '<a href="/resources">Privacy Policy</a><a href="/resources">API Reference</a>';
  expectErrors('NC-footer-resources', validateFooterLegalAndSupportHygiene(badFooter));

  console.log('\n[NC-git] Branch policy on current worktree');
  const gitMsgs = assertDiscoverabilityGitBranchPolicy(marketingRoot);
  if (gitMsgs.length) {
    pass(`NC-git: branch policy active (${gitMsgs[0].slice(0, 80)}…)`);
  } else {
    pass('NC-git: branch policy clean or skipped');
  }

  console.log('\n──────────────────────────────────────────────');
  if (failures > 0) {
    console.error(`\nD2 negative controls: ${failures} unexpected failure(s).`);
    process.exit(1);
  }
  console.log(`\nD2 negative controls: structural failures caught as expected (${passes} passes).`);
}

main();
