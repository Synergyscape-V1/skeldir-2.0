#!/usr/bin/env node

/**
 * Skeldir D4 — structured data (JSON-LD), entity semantics, canonical alignment.
 */

import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { parseArticleSlugsFromContent } from './discoverability/lib/content-slugs.mjs';
import {
  assertDiscoverabilityGitBranchPolicy,
  META_NOINDEX_PUBLIC_PATHS,
} from './discoverability/lib/d2-crawl-graph.mjs';
import {
  loadVerifiedSameAsUrls,
  validateD4IndexablePage,
  validateAllOrganizationIds,
  assertHtmlContainsUnescapedJsonLdLt,
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

function readManifestStaticPaths() {
  const p = path.join(MARKETING_ROOT, 'discoverability.sitemap-manifest.json');
  const j = JSON.parse(fs.readFileSync(p, 'utf8'));
  return j.staticPaths || [];
}

function main() {
  console.log('╔══════════════════════════════════════════════╗');
  console.log('║  Skeldir D4 — Structured data & entity semantics ║');
  console.log('╚══════════════════════════════════════════════╝\n');

  console.log('[0] Git branch policy');
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

  console.log('\n[2] Verified sameAs registry');
  let verifiedSameAs = [];
  try {
    verifiedSameAs = loadVerifiedSameAsUrls(MARKETING_ROOT);
    pass(`entity-profile-registry.json loaded (${verifiedSameAs.length} sameAs URLs)`);
  } catch (e) {
    fail(e.message);
    process.exit(1);
  }

  const staticPaths = readManifestStaticPaths();
  const slugs = parseArticleSlugsFromContent(MARKETING_ROOT);
  const eligible = [...new Set([...staticPaths, ...slugs.map((s) => `/resources/${s}`)])];

  console.log('\n[3] D4 indexable routes — JSON-LD + parity');
  for (const logical of eligible) {
    const rel =
      logical === '/'
        ? 'index.html'
        : logical.startsWith('/resources/')
          ? `resources/${logical.slice('/resources/'.length)}.html`
          : `${logical.replace(/^\//, '')}.html`;
    const abs = path.join(MARKETING_ROOT, 'out', rel.split('/').join(path.sep));
    if (!fs.existsSync(abs)) {
      fail(`missing built HTML for ${logical} (${rel})`);
      continue;
    }
    const html = fs.readFileSync(abs, 'utf8');
    const ltErrs = assertHtmlContainsUnescapedJsonLdLt(html);
    if (ltErrs.length) ltErrs.forEach((e) => fail(`${logical}: ${e}`));
    const verr = validateD4IndexablePage(MARKETING_ROOT, logical, html, verifiedSameAs);
    if (verr.length) verr.forEach((e) => fail(`${logical}: ${e}`));
    if (!ltErrs.length && !verr.length) pass(`${logical}`);
  }

  console.log('\n[4] Organization @id global consistency');
  const oidErrs = validateAllOrganizationIds(MARKETING_ROOT);
  if (oidErrs.length) oidErrs.forEach(fail);
  else pass('all Organization @id nodes use canonical fragment');

  console.log('\n[5] Noindex / placeholder surfaces — no forbidden rich schema');
  for (const pth of META_NOINDEX_PUBLIC_PATHS) {
    const rel =
      pth === '/'
        ? 'index.html'
        : pth.startsWith('/resources/')
          ? `resources/${pth.slice('/resources/'.length)}.html`
          : `${pth.replace(/^\//, '')}.html`;
    const abs = path.join(MARKETING_ROOT, 'out', rel.split('/').join(path.sep));
    if (!fs.existsSync(abs)) continue;
    const html = fs.readFileSync(abs, 'utf8');
    const errs = validateD4IndexablePage(MARKETING_ROOT, pth, html, verifiedSameAs);
    errs.forEach((e) => fail(`noindex surface ${pth}: ${e}`));
  }
  pass('META_NOINDEX_PUBLIC_PATHS scanned');

  console.log('\n[6] URL authority module present');
  const crawlSrc = fs.readFileSync(path.join(MARKETING_ROOT, 'src', 'lib', 'crawlUrls.ts'), 'utf8');
  if (!/export const SITE_ORIGIN/.test(crawlSrc)) fail('crawlUrls.ts missing SITE_ORIGIN');
  else pass('crawlUrls.ts exports SITE_ORIGIN');

  console.log('\n──────────────────────────────────────────────');
  console.log(`Passes: ${passes}  Failures: ${failures}`);
  if (failures > 0) process.exit(1);
}

main();
