#!/usr/bin/env node

/**
 * Skeldir D2 — crawl graph, sitemap, robots, canonicals, noindex boundaries, footer hygiene.
 */

import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { parseArticleSlugsFromContent } from './discoverability/lib/content-slugs.mjs';
import {
  parseSitemapLocs,
  validateSitemapXmlWellFormed,
  validateSitemapMatchesExpected,
  validateRobotsPolicy,
  extractCanonicalHrefs,
  sitemapPathToOutRelative,
  htmlHasNoindexRobots,
  validateFooterLegalAndSupportHygiene,
  assertDiscoverabilityGitBranchPolicy,
} from './discoverability/lib/d2-crawl-graph.mjs';
import { validateResourcesHubAnchors, validateBookDemoSitemapContainment } from './discoverability/lib/d1-html-retrieval.mjs';

const MARKETING_ROOT = process.cwd();
const OUT_DIR = path.join(MARKETING_ROOT, 'out');
const REGISTRY_PATH = path.join(MARKETING_ROOT, 'discoverability.routes.json');

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

function locToCanonicalPath(loc) {
  const u = new URL(loc);
  return u.pathname || '/';
}

function main() {
  console.log('╔══════════════════════════════════════════════╗');
  console.log('║  Skeldir D2 — Crawl graph & index control     ║');
  console.log('╚══════════════════════════════════════════════╝\n');

  console.log('[0] Git branch policy (isolated feature branch)');
  const gitErrs = assertDiscoverabilityGitBranchPolicy(MARKETING_ROOT);
  if (gitErrs.length) {
    for (const e of gitErrs) fail(e);
  } else pass('Git branch policy satisfied (or skipped)');

  console.log('\n[1] Production build');
  const build = spawnSync('npm run build', {
    cwd: MARKETING_ROOT,
    shell: true,
    stdio: 'inherit',
  });
  if (build.status !== 0) {
    fail('npm run build exited non-zero');
    process.exit(1);
  }
  pass('npm run build completed');

  console.log('\n[2] Sitemap file presence & XML');
  const sitemapPath = path.join(OUT_DIR, 'sitemap.xml');
  if (!fs.existsSync(sitemapPath)) {
    fail('out/sitemap.xml missing');
    process.exit(1);
  }
  const sitemapXml = fs.readFileSync(sitemapPath, 'utf8');
  const wf = validateSitemapXmlWellFormed(sitemapXml);
  if (wf.length) {
    for (const e of wf) fail(e);
  } else pass('sitemap XML structure and locs look valid');

  const locs = parseSitemapLocs(sitemapXml);
  const smErrs = validateSitemapMatchesExpected(MARKETING_ROOT, locs);
  if (smErrs.length) {
    for (const e of smErrs) fail(e);
  } else pass('sitemap URLs match discoverability manifest + articlesData slugs');

  console.log('\n[3] robots.txt');
  const robotsPath = path.join(OUT_DIR, 'robots.txt');
  if (!fs.existsSync(robotsPath)) {
    fail('out/robots.txt missing');
    process.exit(1);
  }
  const robotsTxt = fs.readFileSync(robotsPath, 'utf8');
  const rb = validateRobotsPolicy(robotsTxt);
  if (rb.length) {
    for (const e of rb) fail(e);
  } else pass('robots.txt policy-safe and references sitemap');

  console.log('\n[4] Registry /book-demo sitemap containment (D0)');
  const registry = JSON.parse(fs.readFileSync(REGISTRY_PATH, 'utf8'));
  const bdErrs = validateBookDemoSitemapContainment(registry);
  if (bdErrs.length) {
    for (const e of bdErrs) fail(e);
  } else pass('/book-demo registry containment OK');

  console.log('\n[5] Canonical tags match sitemap URLs');
  for (const loc of locs) {
    const pathname = locToCanonicalPath(loc);
    const rel = sitemapPathToOutRelative(pathname);
    if (!rel) {
      fail(`cannot map sitemap loc to out file: ${loc}`);
      continue;
    }
    const htmlPath = path.join(OUT_DIR, rel);
    if (!fs.existsSync(htmlPath)) {
      fail(`HTML missing for sitemap URL ${loc} → ${rel}`);
      continue;
    }
    const html = fs.readFileSync(htmlPath, 'utf8');
    const cans = extractCanonicalHrefs(html);
    if (cans.length !== 1) {
      fail(`${rel}: expected exactly 1 canonical, found ${cans.length} (${cans.join(', ')})`);
      continue;
    }
    const norm = (u) => {
      const x = new URL(u);
      let p = x.pathname;
      if (p.length > 1 && p.endsWith('/')) p = p.slice(0, -1);
      return `${x.origin}${p}`;
    };
    if (norm(cans[0]) !== norm(loc)) {
      fail(`${rel}: canonical ${cans[0]} does not match sitemap loc ${loc}`);
    } else pass(`${rel}: canonical matches sitemap`);
  }

  console.log('\n[6] Noindex boundaries (auth, thank-you, review artifacts)');
  const loginHtml = path.join(OUT_DIR, 'Login.html');
  const signupHtml = path.join(OUT_DIR, 'signup.html');
  const tyHtml = path.join(OUT_DIR, 'book-demo', 'thank-you.html');
  for (const [label, p] of [
    ['Login', loginHtml],
    ['signup', signupHtml],
    ['book-demo/thank-you', tyHtml],
  ]) {
    if (!fs.existsSync(p)) {
      fail(`missing ${label} HTML at ${p}`);
      continue;
    }
    const h = fs.readFileSync(p, 'utf8');
    if (!htmlHasNoindexRobots(h)) fail(`${label} missing noindex robots meta`);
    else pass(`${label} has noindex`);
  }

  const impl = path.join(OUT_DIR, 'implementations', 'agent-a', 'index.html');
  if (fs.existsSync(impl)) {
    const ih = fs.readFileSync(impl, 'utf8');
    if (!htmlHasNoindexRobots(ih)) fail('implementations/agent-a missing noindex');
    else pass('implementations/agent-a carries noindex');
  } else fail('implementations/agent-a/index.html missing from export');

  console.log('\n[7] Resources hub article anchors');
  const hubPath = path.join(OUT_DIR, 'resources.html');
  const hub = fs.readFileSync(hubPath, 'utf8');
  const slugs = parseArticleSlugsFromContent(MARKETING_ROOT);
  const hubErrs = validateResourcesHubAnchors(hub, slugs);
  if (hubErrs.length) {
    for (const e of hubErrs) fail(e);
  } else pass('resources hub links every article slug');

  console.log('\n[8] Footer legal/support link hygiene (built homepage)');
  const indexHtml = fs.readFileSync(path.join(OUT_DIR, 'index.html'), 'utf8');
  const fe = validateFooterLegalAndSupportHygiene(indexHtml);
  if (fe.length) {
    for (const e of fe) fail(e);
  } else pass('homepage footer legal/support links are truthful');

  console.log('\n[9] book-demo must not appear in sitemap');
  if (locs.some((l) => locToCanonicalPath(l).replace(/\/$/, '') === '/book-demo')) {
    fail('/book-demo must not be listed in sitemap while contained');
  } else pass('/book-demo absent from sitemap');

  console.log('\n──────────────────────────────────────────────');
  if (failures > 0) {
    console.error(`\nD2 harness: ${failures} failure(s), ${passes} pass(es).`);
    process.exit(1);
  }
  console.log(`\nD2 harness: all checks passed (${passes} passes).`);
}

main();
