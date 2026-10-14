#!/usr/bin/env node

/**
 * D3 negative controls — proves bot-policy / robots alignment validators fire on corruption.
 */

import fs from 'node:fs';
import path from 'node:path';
import {
  validateRobotsPolicy,
  readCrawlUrlAuthority,
} from './discoverability/lib/d2-crawl-graph.mjs';
import {
  loadBotPolicyManifest,
  validateBotManifestSchema,
  validatePolicyRobotsAlignmentCore,
  validateRobotsDisallowNoSensitiveLeaks,
} from './discoverability/lib/d3-bot-policy.mjs';

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
  console.log('║  Skeldir D3 — Negative control proof            ║');
  console.log('╚══════════════════════════════════════════════╝\n');

  const marketingRoot = process.cwd();
  const auth = readCrawlUrlAuthority(marketingRoot);

  const manifest = loadBotPolicyManifest(marketingRoot);

  const badManifest = JSON.parse(JSON.stringify(manifest));
  delete badManifest.bots;
  expectErrors('NC-D3-01 missing bots array', validateBotManifestSchema(badManifest));

  const badManifest2 = JSON.parse(JSON.stringify(manifest));
  badManifest2.bots = (badManifest2.bots || []).filter((b) => b.id !== 'gptbot');
  expectErrors('NC-D3-02 required gptbot id removed', validateBotManifestSchema(badManifest2));

  const badManifest3 = JSON.parse(JSON.stringify(manifest));
  const gpt = badManifest3.bots.find((b) => b.id === 'gptbot');
  if (gpt) {
    gpt.functional_tier = 'tier3_training_bulk_reuse';
    gpt.policy = 'allow';
  }
  expectErrors('NC-D3-03 tier3 training bot marked allow', validateBotManifestSchema(badManifest3));

  const badManifest4 = JSON.parse(JSON.stringify(manifest));
  const oai = badManifest4.bots.find((b) => b.id === 'oai_searchbot');
  if (oai) {
    oai.functional_tier = 'tier1_search_index_retrieval';
    oai.policy = 'disallow';
  }
  expectErrors('NC-D3-04 tier1 retrieval bot marked disallow', validateBotManifestSchema(badManifest4));

  const goodRobots = fs.readFileSync(path.join(marketingRoot, 'out', 'robots.txt'), 'utf8');
  const misaligned = `User-agent: OAI-SearchBot\nDisallow: /\n\nUser-agent: *\nAllow: /\nSitemap: ${auth.SITE_ORIGIN}/sitemap.xml\n`;
  expectErrors(
    'NC-D3-05 OAI-SearchBot blocked vs manifest allow',
    validatePolicyRobotsAlignmentCore(manifest, misaligned),
  );

  const misaligned2 = `User-agent: GPTBot\nAllow: /\n\nUser-agent: *\nAllow: /\nSitemap: ${auth.SITE_ORIGIN}/sitemap.xml\n`;
  expectErrors(
    'NC-D3-06 GPTBot allowed vs manifest disallow',
    validatePolicyRobotsAlignmentCore(manifest, misaligned2),
  );

  const noSitemap = 'User-agent: *\nAllow: /\n';
  expectErrors('NC-D3-07 robots missing sitemap', validateRobotsPolicy(noSitemap, marketingRoot));

  const adminLeak = `User-agent: *\nAllow: /\nDisallow: /admin\nSitemap: ${auth.SITE_ORIGIN}/sitemap.xml\n`;
  expectErrors('NC-D3-08 sensitive disallow /admin', validateRobotsDisallowNoSensitiveLeaks(adminLeak));

  if (!fs.existsSync(path.join(marketingRoot, 'out', 'robots.txt'))) {
    fail('out/robots.txt missing — run npm run build before discoverability:d3:negative-controls');
  } else {
    const alignGood = validatePolicyRobotsAlignmentCore(manifest, goodRobots);
    if (alignGood.length) {
      alignGood.forEach(fail);
    } else pass('golden out/robots.txt still aligns with manifest (sanity)');
  }

  console.log('\n──────────────────────────────────────────────');
  console.log(`Passes: ${passes}  Failures: ${failures}`);
  if (failures > 0) process.exit(1);
}

main();
