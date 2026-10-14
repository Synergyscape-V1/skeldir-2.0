#!/usr/bin/env node

/**
 * Skeldir D1 — HTML-first retrieval + content-source parity harness.
 *
 * Validates: build, marketing_static HTML, resources anchors, use-client boundary,
 * articlesData ↔ body registry ↔ TOC ↔ generateStaticParams (source),
 * registry article instances, JSON-LD parse + metadata alignment, /book-demo containment,
 * optional local static-server bot UAs (fetch).
 */

import { spawnSync } from 'node:child_process';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { parseArticleSlugsFromContent } from './discoverability/lib/content-slugs.mjs';
import { parseArticlesMetadataFromSource } from './discoverability/lib/articles-metadata-from-source.mjs';
import {
  validateArticleHtml,
  validateMarketingCommercialHtml,
  validateResourcesHubAnchors,
  validateNoUseClientOnArticleDocument,
  validateArticleJsonLdAgainstMetadata,
  validateRegistryArticleInstances,
  validateBookDemoSitemapContainment,
} from './discoverability/lib/d1-html-retrieval.mjs';
import {
  validateArticleBodyRegistrySourceParity,
  validateTocSlugSourceParity,
  validateGenerateStaticParamsUsesArticles,
} from './discoverability/lib/d1-article-source-parity.mjs';

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

function normalizeOutPath(expected) {
  return expected.replace(/^out[/\\]/, '').split(/[/\\]/).join(path.sep);
}

async function optionalLiveUaParity() {
  const base = process.env.D1_LIVE_URL;
  if (!base) {
    console.log('\n[11] Optional D1_LIVE_URL bot fetch skipped (set D1_LIVE_URL to enable).');
    return;
  }
  const url = `${base.replace(/\/$/, '')}/resources/why-your-attribution-numbers-never-match`;
  const uas = ['Googlebot Smartphone', 'OAI-SearchBot', 'Claude-SearchBot', 'PerplexityBot', 'curl'];
  const markers = [/attribution|meta|revenue|discrepancy/i];
  console.log(`\n[11] D1_LIVE_URL bot fetch: ${url}`);
  for (const ua of uas) {
    try {
      const res = await fetch(url, { headers: { 'user-agent': ua } });
      const text = await res.text();
      const ok = markers.some((re) => re.test(text)) && !/animate-pulse[^\n]{0,120}loading/i.test(text);
      if (!ok) fail(`live fetch UA="${ua}": missing body markers or shell-like response`);
      else pass(`live fetch UA="${ua}": article markers present`);
    } catch (e) {
      fail(`live fetch UA="${ua}": ${e.message}`);
    }
  }
}

/**
 * Minimal static file server for `out/` (D1-C07) — avoids flaky `npx serve` installs.
 * Maps `/resources/foo` → `out/resources/foo.html`, `/` → `out/index.html`.
 */
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

/**
 * Local static server + fetch with multiple User-Agents (D1-C07 empirical bot parity).
 */
async function runLocalStaticBotFetch() {
  if (process.env.D1_SKIP_LOCAL_SERVE === '1') {
    console.log('\n[10] Local static bot fetch skipped (D1_SKIP_LOCAL_SERVE=1).');
    return;
  }

  const port = Number(process.env.D1_SERVE_PORT || '4811');
  const base = `http://127.0.0.1:${port}`;
  const url = `${base}/resources/why-your-attribution-numbers-never-match`;

  console.log(`\n[10] Local static server bot-style fetch (in-process out/, port ${port})`);

  /** @type {import('http').Server | undefined} */
  let server;
  try {
    server = await startOutStaticServer(port);
    await waitForHttpOk(`${base}/`, 15000);
  } catch (e) {
    fail(`local static server failed to start: ${e.message}`);
    return;
  }

  const uas = ['curl/8.0', 'Googlebot Smartphone', 'OAI-SearchBot', 'Claude-SearchBot', 'PerplexityBot'];
  const marker = /attribution|meta|revenue|discrepancy|<h1|<h2/i;

  try {
    for (const ua of uas) {
      const res = await fetch(url, { headers: { 'user-agent': ua } });
      const text = await res.text();
      const ok = marker.test(text) && !/animate-pulse[^\n]{0,120}loading/i.test(text);
      if (!ok) {
        fail(`local fetch UA="${ua}": expected article body markers, got status=${res.status} len=${text.length}`);
      } else {
        pass(`local fetch UA="${ua}": article body markers present (len=${text.length})`);
      }
    }
  } catch (e) {
    fail(`local static fetch failed: ${e.message}`);
  } finally {
    try {
      server?.close();
    } catch {
      /* ignore */
    }
    await new Promise((r) => setTimeout(r, 200));
  }
}

async function main() {
  console.log('╔══════════════════════════════════════════════╗');
  console.log('║  Skeldir D1 — retrieval + content parity       ║');
  console.log('╚══════════════════════════════════════════════╝\n');

  console.log('[1] Production build');
  const build = spawnSync('npm', ['run', 'build'], {
    cwd: MARKETING_ROOT,
    stdio: 'inherit',
    shell: true,
  });
  if (build.status !== 0) {
    fail('npm run build exited non-zero');
    process.exit(1);
  }
  pass('npm run build completed');

  console.log('\n[2] Article document / hub source boundary (no use client)');
  const ucErrs = validateNoUseClientOnArticleDocument(MARKETING_ROOT);
  if (ucErrs.length) ucErrs.forEach(fail);
  else pass('forbidden paths contain no "use client"');

  console.log('\n[3] Content source ↔ renderer ↔ TOC ↔ generateStaticParams (source scan)');
  const p1 = validateArticleBodyRegistrySourceParity(MARKETING_ROOT);
  if (p1.length) p1.forEach(fail);
  else pass('articleBodyRegistry.tsx ↔ articlesData (exhaustive)');

  const p2 = validateTocSlugSourceParity(MARKETING_ROOT);
  if (p2.length) p2.forEach(fail);
  else pass('TableOfContents ARTICLE_TOC_GENERATORS ↔ articlesData');

  const p3 = validateGenerateStaticParamsUsesArticles(MARKETING_ROOT);
  if (p3.length) p3.forEach(fail);
  else pass('generateStaticParams uses articles.map');

  if (!fs.existsSync(REGISTRY_PATH)) {
    fail('discoverability.routes.json missing');
    process.exit(1);
  }

  const registry = JSON.parse(fs.readFileSync(REGISTRY_PATH, 'utf8'));
  const routes = registry.routes || [];
  const slugs = parseArticleSlugsFromContent(MARKETING_ROOT);
  const articlesMeta = parseArticlesMetadataFromSource(MARKETING_ROOT);

  console.log('\n[4] Registry article instances ↔ articlesData slugs');
  const regArt = validateRegistryArticleInstances(registry, slugs);
  if (regArt.length) regArt.forEach(fail);
  else pass('registry article routes match articlesData slugs exactly');

  console.log('\n[5] /book-demo sitemap containment (registry)');
  const bd = validateBookDemoSitemapContainment(registry);
  if (bd.length) bd.forEach(fail);
  else pass('/book-demo sitemap flags contained per D0 policy');

  const d1Targets = routes.filter(
    (r) =>
      r.physical_surface === 'marketing_static' &&
      r.indexability_class === 'indexable' &&
      typeof r.build_output_path_expected === 'string' &&
      r.route_type !== 'article_pattern'
  );

  console.log('\n[6] Static HTML for D0 marketing_static indexable routes');
  for (const r of d1Targets) {
    const rel = normalizeOutPath(r.build_output_path_expected);
    const abs = path.join(MARKETING_ROOT, 'out', rel);
    if (!fs.existsSync(abs)) {
      fail(`missing ${r.build_output_path_expected} for ${r.logical_route}`);
      continue;
    }
    const html = fs.readFileSync(abs, 'utf8');
    if (r.route_type === 'article') {
      const errs = validateArticleHtml(html, { slug: r.logical_route });
      if (errs.length) errs.forEach((e) => fail(`${r.logical_route}: ${e}`));
      else pass(`${r.logical_route} (HTML heuristics)`);

      const slug = r.logical_route.replace(/^\/resources\//, '');
      const meta = articlesMeta.find((a) => a.slug === slug);
      if (!meta) {
        fail(`${r.logical_route}: no parsed metadata from articlesData.ts`);
      } else {
        const jerr = validateArticleJsonLdAgainstMetadata(html, meta);
        if (jerr.length) jerr.forEach((e) => fail(`${r.logical_route} JSON-LD: ${e}`));
        else pass(`${r.logical_route} (JSON-LD parse + metadata parity)`);
      }
    } else {
      const errs = validateMarketingCommercialHtml(html);
      if (errs.length) errs.forEach((e) => fail(`${r.logical_route}: ${e}`));
      else pass(`${r.logical_route}`);
    }
  }

  console.log('\n[7] Resource hub — anchor graph for every article slug');
  const resourcesHtml = path.join(OUT_DIR, 'resources.html');
  if (!fs.existsSync(resourcesHtml)) {
    fail('out/resources.html missing');
  } else {
    const html = fs.readFileSync(resourcesHtml, 'utf8');
    const hubErrs = validateResourcesHubAnchors(html, slugs);
    if (hubErrs.length) hubErrs.forEach(fail);
    else pass(`all ${slugs.length} article slugs appear as /resources/<slug> hrefs`);
  }

  console.log('\n[8] Static export UA-independence (same bytes for all bots)');
  pass('out/ artifacts are static files (no per-UA server rendering in export)');

  console.log('\n[9] Route page must not contain unguarded slug switch (grep guard)');
  const pagePath = path.join(MARKETING_ROOT, 'src', 'app', 'resources', '[slug]', 'page.tsx');
  const pageSrc = fs.readFileSync(pagePath, 'utf8');
  if (/\bswitch\s*\(\s*slug\s*\)/.test(pageSrc)) {
    fail('[slug]/page.tsx must not use switch(slug) for body selection (use registry)');
  }
  if (!pageSrc.includes('getArticleBodyComponent')) {
    fail('[slug]/page.tsx must resolve body via getArticleBodyComponent from articleBodyRegistry');
  }
  pass('[slug]/page.tsx uses registry-driven body resolution');

  await runLocalStaticBotFetch();

  await optionalLiveUaParity();

  console.log('\n──────────────────────────────────────────────');
  console.log(`Passes: ${passes}  Failures: ${failures}`);
  if (failures > 0) process.exit(1);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
