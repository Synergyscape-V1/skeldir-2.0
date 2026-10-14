#!/usr/bin/env node

/**
 * Skeldir D3 — AI retrieval access, bot policy matrix, robots alignment, static HTML parity fetches.
 */

import { spawnSync } from 'node:child_process';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import {
  validateRobotsPolicy,
  validateRobotsDoesNotBlockMetaNoindexRoutes,
  META_NOINDEX_PUBLIC_PATHS,
  assertDiscoverabilityGitBranchPolicy,
  validateRobotsSitemapUrlMatchesAuthority,
  validateRobotsSourceStaticAndNoLiteralOrigin,
  htmlHasNoindexRobots,
} from './discoverability/lib/d2-crawl-graph.mjs';
import {
  loadBotPolicyManifest,
  validateBotManifestSchema,
  validatePolicyRobotsAlignmentCore,
} from './discoverability/lib/d3-bot-policy.mjs';

const MARKETING_ROOT = process.cwd();
const OUT_DIR = path.join(MARKETING_ROOT, 'out');
const ROBOTS_SRC = path.join(MARKETING_ROOT, 'src', 'app', 'robots.ts');

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

function startOutStaticServer(port) {
  const outRoot = OUT_DIR;
  const server = http.createServer((req, res) => {
    try {
      let urlPath = (req.url || '/').split('?')[0];
      if (urlPath === '/') urlPath = '/index.html';
      const rel = urlPath.replace(/^\//, '');
      let filePath = path.join(outRoot, rel);
      if (!path.extname(filePath)) {
        filePath += '.html';
      }
      if (!filePath.startsWith(outRoot)) {
        res.statusCode = 403;
        res.end('Forbidden');
        return;
      }
      if (!fs.existsSync(filePath)) {
        res.statusCode = 404;
        res.end('Not found');
        return;
      }
      res.setHeader('Content-Type', 'text/html; charset=utf-8');
      fs.createReadStream(filePath).pipe(res);
    } catch {
      res.statusCode = 500;
      res.end('Error');
    }
  });

  return new Promise((resolve, reject) => {
    server.listen(port, '127.0.0.1', () => resolve(server));
    server.on('error', reject);
  });
}

async function waitForHttpOk(url, timeoutMs = 20000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(url, { signal: AbortSignal.timeout(2000) });
      if (res.status >= 200 && res.status < 500) return;
    } catch {
      /* retry */
    }
    await new Promise((r) => setTimeout(r, 400));
  }
  throw new Error(`timeout waiting for HTTP from ${url}`);
}

async function runLocalStaticFetchMatrix(manifest) {
  if (process.env.D3_SKIP_LOCAL_SERVE === '1') {
    console.log('\n[6] Local static fetch matrix skipped (D3_SKIP_LOCAL_SERVE=1).');
    return;
  }

  const suite = manifest.d3_url_fetch_suite || {};
  const paths = Array.isArray(suite.paths) ? suite.paths : [];
  if (!paths.length) {
    fail('d3_url_fetch_suite.paths missing');
    return;
  }

  const shellRe = new RegExp(suite.article_shell_forbidden || '(?!a)a', 'i');
  const wafRe = new RegExp(suite.waf_challenge_heuristic || '(?!a)a', 'i');
  const articleMarkers = new RegExp(suite.article_body_markers || 'body', 'i');
  const genericMarkers = new RegExp(suite.generic_body_markers || '<html', 'i');
  const articleOnly = new Set(suite.article_paths_only || []);

  const bots = (manifest.bots || []).filter((b) => b.include_in_local_static_fetch_matrix);
  if (!bots.length) {
    fail('no bots with include_in_local_static_fetch_matrix');
    return;
  }

  const port = Number(process.env.D3_SERVE_PORT || '4813');
  const base = `http://127.0.0.1:${port}`;

  console.log(`\n[6] D3 local static fetch matrix (port ${port}, UA list from manifest)`);

  /** @type {import('http').Server | undefined} */
  let server;
  try {
    server = await startOutStaticServer(port);
    await waitForHttpOk(`${base}/`, 15000);
  } catch (e) {
    fail(`local static server failed: ${e.message}`);
    return;
  }

  try {
    for (const routePath of paths) {
      const url = `${base}${routePath}`;
      const isArticle = articleOnly.has(routePath);

      for (const b of bots) {
        const ua = b.fetch_test_user_agent || b.user_agent_token;
        const res = await fetch(url, { headers: { 'user-agent': ua } });
        const text = await res.text();
        const marker = isArticle ? articleMarkers : genericMarkers;

        if (res.status !== 200) {
          fail(`fetch ${routePath} UA="${ua}" status=${res.status}`);
          continue;
        }
        if (shellRe.test(text)) {
          fail(`fetch ${routePath} UA="${ua}": loading-shell heuristic matched`);
          continue;
        }
        if (wafRe.test(text)) {
          fail(`fetch ${routePath} UA="${ua}": WAF/challenge heuristic matched`);
          continue;
        }
        if (!marker.test(text)) {
          fail(`fetch ${routePath} UA="${ua}": body markers missing`);
          continue;
        }
        if (isArticle && htmlHasNoindexRobots(text)) {
          fail(`fetch ${routePath} UA="${ua}": unexpected noindex on indexable article surface`);
          continue;
        }
        pass(`fetch ${routePath} UA="${b.user_agent_token}": OK (len=${text.length})`);
      }
    }
  } catch (e) {
    fail(`fetch matrix error: ${e.message}`);
  } finally {
    try {
      server?.close();
    } catch {
      /* ignore */
    }
    await new Promise((r) => setTimeout(r, 200));
  }
}

async function optionalLiveFetches(manifest) {
  const base = process.env.D3_LIVE_URL;
  if (!base) {
    console.log('\n[7] D3_LIVE_URL deploy/preview fetch skipped (set D3_LIVE_URL for Gate D3.4 evidence).');
    return;
  }
  const origin = base.replace(/\/$/, '');
  const suite = manifest.d3_url_fetch_suite || {};
  const articlePath = '/resources/why-your-attribution-numbers-never-match';
  const articleMarkers = new RegExp(suite.article_body_markers || 'body', 'i');
  const shellRe = new RegExp(suite.article_shell_forbidden || '(?!a)a', 'i');
  const wafRe = new RegExp(suite.waf_challenge_heuristic || '(?!a)a', 'i');

  const uas = ['OAI-SearchBot', 'ChatGPT-User', 'ClaudeBot', 'PerplexityBot'];

  console.log(`\n[7] D3_LIVE_URL deploy checks: ${origin}`);

  try {
    const rRobots = await fetch(`${origin}/robots.txt`, { headers: { 'user-agent': 'curl' } });
    const rt = await rRobots.text();
    if (rRobots.status !== 200) fail(`live robots.txt status=${rRobots.status}`);
    else pass(`live robots.txt status=200 len=${rt.length}`);
  } catch (e) {
    fail(`live robots.txt: ${e.message}`);
  }

  for (const ua of uas) {
    const url = `${origin}${articlePath}`;
    try {
      const res = await fetch(url, { headers: { 'user-agent': ua } });
      const text = await res.text();
      const ok =
        res.status === 200 &&
        articleMarkers.test(text) &&
        !shellRe.test(text) &&
        !wafRe.test(text);
      if (!ok) fail(`live ${ua}: status=${res.status} markers/shell/waf check failed`);
      else pass(`live ${ua}: article body heuristics OK`);
    } catch (e) {
      fail(`live ${ua}: ${e.message}`);
    }
  }
}

async function main() {
  console.log('╔══════════════════════════════════════════════╗');
  console.log('║  Skeldir D3 — Bot policy & retrieval parity    ║');
  console.log('╚══════════════════════════════════════════════╝\n');

  console.log('[0] Git branch policy (shared with D2 harness semantics)');
  const gitErrs = assertDiscoverabilityGitBranchPolicy(MARKETING_ROOT);
  if (gitErrs.length) gitErrs.forEach(fail);
  else pass('Git branch policy satisfied (or CI skip)');

  let manifest;
  try {
    manifest = loadBotPolicyManifest(MARKETING_ROOT);
  } catch (e) {
    fail(e.message);
    process.exit(1);
  }

  console.log('\n[0b] D2 dependency / production-final gate (informational)');
  const d2 = manifest.d2_dependency || {};
  console.log(`      d2 local mechanism: ${d2.local_mechanism_state ?? 'unknown'}`);
  console.log(`      d2 main/CI: ${d2.main_merge_ci_state ?? 'unknown'}`);
  console.log(`      d2 deploy/preview: ${d2.deploy_preview_state ?? 'unknown'}`);
  console.log(`      D3 production-final blocked by D2: ${d2.d3_production_final_blocked_by_d2 === true ? 'yes' : 'no'}`);
  console.log(`      llms.txt scope note: ${manifest.llms_txt_scope || '(missing)'}`);

  console.log('\n[1] Bot policy manifest schema');
  const schemaErrs = validateBotManifestSchema(manifest);
  if (schemaErrs.length) schemaErrs.forEach(fail);
  else pass('discoverability.bot-policy.json schema OK');

  console.log('\n[2] robots.ts must import machine policy (no drift)');
  if (!fs.existsSync(ROBOTS_SRC)) fail('robots.ts missing');
  else {
    const rs = fs.readFileSync(ROBOTS_SRC, 'utf8');
    if (!rs.includes('discoverability.bot-policy.json')) {
      fail('robots.ts must import discoverability.bot-policy.json');
    } else pass('robots.ts imports discoverability.bot-policy.json');
    const roSrcErrs = validateRobotsSourceStaticAndNoLiteralOrigin(MARKETING_ROOT);
    if (roSrcErrs.length) roSrcErrs.forEach(fail);
    else pass('robots.ts static export + no literal origin (D2 contract)');
  }

  console.log('\n[3] Production build');
  const build = spawnSync('npm', ['run', 'build'], {
    cwd: MARKETING_ROOT,
    shell: true,
    stdio: 'inherit',
  });
  if (build.status !== 0) {
    fail('npm run build exited non-zero');
    process.exit(1);
  }
  pass('npm run build completed');

  const robotsPath = path.join(OUT_DIR, 'robots.txt');
  if (!fs.existsSync(robotsPath)) {
    fail('out/robots.txt missing after build');
    process.exit(1);
  }
  const robotsBody = fs.readFileSync(robotsPath, 'utf8');

  console.log('\n[4] D2 robots hygiene + meta-noindex crawlability law');
  const rp = validateRobotsPolicy(robotsBody, MARKETING_ROOT);
  if (rp.length) rp.forEach(fail);
  else pass('validateRobotsPolicy (D2)');

  const rsm = validateRobotsSitemapUrlMatchesAuthority(robotsBody, MARKETING_ROOT);
  if (rsm.length) rsm.forEach(fail);
  else pass('robots Sitemap URL matches crawl authority');

  const rnx = validateRobotsDoesNotBlockMetaNoindexRoutes(robotsBody, META_NOINDEX_PUBLIC_PATHS);
  if (rnx.length) rnx.forEach(fail);
  else pass('robots does not block meta-noindex public routes');

  console.log('\n[5] D3 robots ↔ manifest alignment + sensitive disallow scan');
  const align = validatePolicyRobotsAlignmentCore(manifest, robotsBody);
  if (align.length) align.forEach(fail);
  else pass('robots.txt matches discoverability.bot-policy.json');

  await runLocalStaticFetchMatrix(manifest);

  await optionalLiveFetches(manifest);

  console.log('\n──────────────────────────────────────────────');
  console.log(`Passes: ${passes}  Failures: ${failures}`);
  if (failures > 0) process.exit(1);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
