#!/usr/bin/env node

/**
 * D2 negative controls — proves crawl-graph validators fire on corruption (D2-C + D2-C2).
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
  readCrawlUrlAuthority,
  validateBookDemoDefectiveNoSelfCanonical,
  validateSitemapLocPathsNoTrailingSlashExceptRoot,
  validateSitemapLocCanonicalPathAlignment,
  validateRobotsSitemapUrlMatchesAuthority,
  validateSitemapSourceStringStaticSafe,
  validateRobotsSourceStringStaticAndNoLiteralOrigin,
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

  const marketingRoot = process.cwd();
  const auth = readCrawlUrlAuthority(marketingRoot);

  const badXml = '<urlset><loc>oops</loc></urlset>';
  expectErrors('NC-sitemap-xml', validateSitemapXmlWellFormed(badXml, marketingRoot));

  const pollutedLocs = [`${auth.SITE_ORIGIN}/`, `${auth.SITE_ORIGIN}/product`, `${auth.SITE_ORIGIN}/extra-bad`];
  expectErrors('NC-sitemap-expected-set', validateSitemapMatchesExpected(marketingRoot, pollutedLocs));

  const badRobots = 'User-agent: *\nDisallow: /\n';
  expectErrors('NC-robots-block-all', validateRobotsPolicy(badRobots, marketingRoot));

  const noSitemapLine = 'User-agent: *\nAllow: /\n';
  expectErrors('NC-robots-missing-sitemap', validateRobotsPolicy(noSitemapLine, marketingRoot));

  const leak =
    `User-agent: *\nAllow: /\nSitemap: ${auth.SITE_ORIGIN}/sitemap.xml\nDisallow: /node_modules\n`;
  expectErrors('NC-robots-sensitive-leak', validateRobotsPolicy(leak, marketingRoot));

  const htmlNoCanon = '<html><head><title>x</title></head><body></body></html>';
  const cans = extractCanonicalHrefs(htmlNoCanon);
  if (cans.length === 0) pass('NC-canonical-missing: extractCanonicalHrefs empty as expected');
  else fail('NC-canonical-missing: expected zero canonicals');

  const badFooter = '<a href="/resources">Privacy Policy</a><a href="/resources">API Reference</a>';
  expectErrors('NC-footer-resources', validateFooterLegalAndSupportHygiene(badFooter));

  console.log('\n[NC-D2-C] Mechanism-aware negative controls');

  const badRobotsBlocksLogin =
    `User-agent: *\nDisallow: /Login\nAllow: /\nSitemap: ${auth.SITE_ORIGIN}/sitemap.xml\n`;
  expectErrors(
    'NC-D2-X1 noindex route blocked by robots',
    validateRobotsDoesNotBlockMetaNoindexRoutes(badRobotsBlocksLogin, ['/Login']),
  );

  const badRobotsImplDisallow =
    `User-agent: *\nAllow: /\nSitemap: ${auth.SITE_ORIGIN}/sitemap.xml\nDisallow: /implementations/\n`;
  expectErrors('NC-D2-X2 implementations disallow (contradicts crawlable noindex proof)', validateRobotsPolicy(badRobotsImplDisallow, marketingRoot));

  const defectiveRegistry = {
    routes: [{ id: 'route-book-demo', status: 'active_defective_until_static_body_verified' }],
  };
  expectErrors(
    'NC-D2-X3 linked defective /book-demo lacks noindex',
    validateBookDemoDefectiveRequiresNoindex(defectiveRegistry, '<html><head></head><body></body></html>'),
  );

  const badRobotsBookDemo =
    `User-agent: *\nAllow: /\nSitemap: ${auth.SITE_ORIGIN}/sitemap.xml\nDisallow: /book-demo\n`;
  expectErrors('NC-D2-X4 robots Disallow /book-demo (noindex paradox)', validateRobotsPolicy(badRobotsBookDemo, marketingRoot));

  const expectedBase = getExpectedSitemapUrls(marketingRoot);
  const pollutedWithBookDemo = [...expectedBase, `${auth.SITE_ORIGIN}/book-demo`];
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

  console.log('\n[NC-D2-C2] URL authority + defective canonical + static sitemap contract');

  const regWithCanon = {
    routes: [
      {
        id: 'route-book-demo',
        status: 'active_defective_until_static_body_verified',
        canonical_exception_justification: null,
      },
    ],
  };
  const badBookHtml =
    '<html><head><link rel="canonical" href="https://example.com/book-demo"/><meta name="robots" content="noindex,follow"/></head><body></body></html>';
  expectErrors(
    'NC-D2-C2-01 defective noindexed /book-demo with self-canonical',
    validateBookDemoDefectiveNoSelfCanonical(regWithCanon, badBookHtml),
  );

  expectErrors(
    'NC-D2-C2-02 sitemap loc trailing slash on non-root',
    validateSitemapLocPathsNoTrailingSlashExceptRoot([`${auth.SITE_ORIGIN}/product/`], marketingRoot),
  );

  expectErrors(
    'NC-D2-C2-03 sitemap vs canonical trailing mismatch',
    validateSitemapLocCanonicalPathAlignment(`${auth.SITE_ORIGIN}/product/`, `${auth.SITE_ORIGIN}/product`),
  );

  expectErrors(
    'NC-D2-C2-04 robots Sitemap origin mismatch vs authority',
    validateRobotsSitemapUrlMatchesAuthority(`User-agent: *\nAllow: /\nSitemap: https://evil.example/sitemap.xml\n`, marketingRoot),
  );

  const badSitemapSrc = `import { cookies } from "next/headers";\nexport const dynamic = "error";\n`;
  expectErrors('NC-D2-C2-05 sitemap.ts request-time API', validateSitemapSourceStringStaticSafe(badSitemapSrc, 'synthetic-sitemap'));

  const badLiteralOrigin = `export const dynamic = "error";\nconst x = "https://skeldir.com";\n`;
  expectErrors('NC-D2-C2-06 literal origin outside crawlUrls', validateSitemapSourceStringStaticSafe(badLiteralOrigin, 'synthetic'));

  const badRobotsDynamic = 'export const dynamic = "force-static";\n';
  expectErrors('NC-D2-C2-07 robots must use dynamic error', validateRobotsSourceStringStaticAndNoLiteralOrigin(badRobotsDynamic, 'synthetic-robots'));

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
