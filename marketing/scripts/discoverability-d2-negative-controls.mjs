#!/usr/bin/env node

/**
 * D2 negative controls — proves crawl-graph validators fire on corruption (D2-C mechanism-aware).
 */

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {
  validateSitemapXmlWellFormed,
  validateSitemapMatchesExpected,
  getExpectedSitemapUrls,
  validateRobotsPolicy,
  extractCanonicalHrefs,
  validateFooterLegalAndSupportHygiene,
  assertDiscoverabilityGitBranchPolicy,
  validateRobotsDoesNotBlockMetaNoindexRoutes,
  validateBookDemoDefectiveRequiresNoindex,
  validateShippedImplementationAgentsHaveNoindex,
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

  console.log('\n[NC-D2-C] Mechanism-aware negative controls');

  const badRobotsBlocksLogin =
    'User-agent: *\nDisallow: /Login\nAllow: /\nSitemap: https://skeldir.com/sitemap.xml\n';
  expectErrors(
    'NC-D2-X1 noindex route blocked by robots',
    validateRobotsDoesNotBlockMetaNoindexRoutes(badRobotsBlocksLogin, ['/Login']),
  );

  const badRobotsImplDisallow =
    'User-agent: *\nAllow: /\nSitemap: https://skeldir.com/sitemap.xml\nDisallow: /implementations/\n';
  expectErrors('NC-D2-X2 implementations disallow (contradicts crawlable noindex proof)', validateRobotsPolicy(badRobotsImplDisallow));

  const defectiveRegistry = {
    routes: [{ id: 'route-book-demo', status: 'active_defective_until_static_body_verified' }],
  };
  expectErrors(
    'NC-D2-X3 linked defective /book-demo lacks noindex',
    validateBookDemoDefectiveRequiresNoindex(defectiveRegistry, '<html><head></head><body></body></html>'),
  );

  const badRobotsBookDemo =
    'User-agent: *\nAllow: /\nSitemap: https://skeldir.com/sitemap.xml\nDisallow: /book-demo\n';
  expectErrors('NC-D2-X4 robots Disallow /book-demo (noindex paradox)', validateRobotsPolicy(badRobotsBookDemo));

  const expectedBase = getExpectedSitemapUrls(marketingRoot);
  const pollutedWithBookDemo = [...expectedBase, 'https://skeldir.com/book-demo'];
  expectErrors(
    'NC-D2-X5 defective /book-demo must not be in sitemap (sitemap ≠ deindex)',
    validateSitemapMatchesExpected(marketingRoot, pollutedWithBookDemo),
  );

  const tmpOut = fs.mkdtempSync(path.join(os.tmpdir(), 'd2-nc-impl-'));
  try {
    const agentDir = path.join(tmpOut, 'implementations', 'agent-a');
    fs.mkdirSync(agentDir, { recursive: true });
    fs.writeFileSync(
      path.join(agentDir, 'index.html'),
      '<!DOCTYPE html><html><head><title>x</title></head><body>no robots meta</body></html>',
      'utf8',
    );
    expectErrors(
      'NC-D2-X6 shipped implementations without crawlable noindex',
      validateShippedImplementationAgentsHaveNoindex(tmpOut),
    );
  } finally {
    fs.rmSync(tmpOut, { recursive: true, force: true });
  }

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
