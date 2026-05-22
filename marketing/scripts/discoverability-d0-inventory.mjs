#!/usr/bin/env node

/**
 * Skeldir D0 — App-Router-Aware Route Inventory Script
 *
 * Usage: node scripts/discoverability-d0-inventory.mjs
 * Or:    npm run discoverability:d0:inventory
 *
 * This script scans:
 * 1. src/app/ for Next.js App Router page routes
 * 2. public/ for static HTML artifacts
 * 3. out/ for build output HTML files
 *
 * It normalizes routes according to App Router conventions:
 * - Route groups (folder) are excluded from URLs
 * - Parallel slots @folder are excluded from URLs
 * - Intercepting routes (.), (..), (...) are handled
 * - Dynamic segments [slug] are represented
 * - generateStaticParams expansion is noted
 *
 * Output: JSON summary of all discovered routes to stdout
 */

import { readdirSync, statSync, existsSync, readFileSync } from 'fs';
import { join, relative, sep, basename, dirname } from 'path';
import { collectRouteTruth } from './discoverability/lib/route-truth.mjs';
import { loadRegistry } from './discoverability/lib/registry-schema.mjs';
import { parseArticleSlugsFromContent } from './discoverability/lib/content-slugs.mjs';

const MARKETING_ROOT = join(process.cwd());
const SRC_APP = join(MARKETING_ROOT, 'src', 'app');
const PUBLIC_DIR = join(MARKETING_ROOT, 'public');
const OUT_DIR = join(MARKETING_ROOT, 'out');

// ────────────────────────────────────────────────────────────
// 1. App Router source scan
// ────────────────────────────────────────────────────────────

function findPageFiles(dir, results = []) {
  if (!existsSync(dir)) return results;
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      // Skip node_modules, .next, etc.
      if (entry.name.startsWith('.') || entry.name === 'node_modules') continue;
      findPageFiles(full, results);
    } else if (entry.name === 'page.tsx' || entry.name === 'page.ts' || entry.name === 'page.jsx' || entry.name === 'page.js') {
      results.push(full);
    }
  }
  return results;
}

/**
 * Normalize an App Router filesystem path to a URL path.
 *
 * Rules:
 * - Route groups: folders matching /^\(.*\)$/ are EXCLUDED from URL
 * - Parallel slots: folders matching /^@/ are EXCLUDED from URL
 * - Intercepting routes: (.), (..), (...) folders are EXCLUDED from URL (route-segment-relative)
 * - Dynamic segments: [param] → :param (kept as-is for registry)
 * - Catch-all: [...param] → :...param
 * - Optional catch-all: [[...param]] → :[[...param]]
 */
function normalizeAppRouterPath(pageFilePath) {
  const rel = relative(SRC_APP, dirname(pageFilePath));
  if (!rel || rel === '.') return '/';

  const segments = rel.split(sep);
  const urlSegments = [];
  const warnings = [];

  for (const seg of segments) {
    // Route groups: (groupName) — excluded from URL
    if (/^\(.*\)$/.test(seg)) {
      // Check for intercepting routes vs route groups
      if (seg === '(.)' || seg === '(..)' || seg === '(...)') {
        warnings.push(`intercepting_route: ${seg}`);
      }
      // Regardless, excluded from URL
      continue;
    }

    // Parallel slots: @slotName — excluded from URL
    if (seg.startsWith('@')) {
      warnings.push(`parallel_slot: ${seg}`);
      continue;
    }

    urlSegments.push(seg);
  }

  const url = '/' + urlSegments.join('/');
  return { url, warnings };
}

function checkUseClient(filePath) {
  try {
    const content = readFileSync(filePath, 'utf-8');
    const firstLines = content.slice(0, 200);
    return firstLines.includes('"use client"') || firstLines.includes("'use client'");
  } catch {
    return false;
  }
}

// ────────────────────────────────────────────────────────────
// 2. Public static scan
// ────────────────────────────────────────────────────────────

function findHtmlFiles(dir, results = []) {
  if (!existsSync(dir)) return results;
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name.startsWith('.') || entry.name === 'node_modules' || entry.name === '_next') continue;
      findHtmlFiles(full, results);
    } else if (entry.name.endsWith('.html') || entry.name.endsWith('.htm')) {
      results.push(full);
    }
  }
  return results;
}

// ────────────────────────────────────────────────────────────
// 3. Main
// ────────────────────────────────────────────────────────────

function main() {
  console.log('=== Skeldir D0 Route Inventory ===\n');

  // --- Source routes ---
  const sourcePages = findPageFiles(SRC_APP);
  const sourceRoutes = sourcePages.map(fp => {
    const result = normalizeAppRouterPath(fp);
    const url = typeof result === 'string' ? result : result.url;
    const warnings = typeof result === 'string' ? [] : result.warnings;
    return {
      source_path: relative(MARKETING_ROOT, fp).replace(/\\/g, '/'),
      resolved_url: url,
      is_client: checkUseClient(fp),
      is_dynamic: url.includes('['),
      warnings,
    };
  });

  console.log('Source Routes (src/app/**/page.tsx):');
  console.log('-----------------------------------');
  for (const r of sourceRoutes) {
    const clientTag = r.is_client ? ' [CLIENT]' : ' [SERVER]';
    const dynamicTag = r.is_dynamic ? ' [DYNAMIC]' : '';
    const warnTag = r.warnings.length > 0 ? ` [WARNINGS: ${r.warnings.join(', ')}]` : '';
    console.log(`  ${r.resolved_url}${clientTag}${dynamicTag}${warnTag}`);
    console.log(`    source: ${r.source_path}`);
  }

  // --- Route group / parallel slot / intercepting route detection ---
  console.log('\nApp Router Special Conventions:');
  console.log('-------------------------------');
  const allDirs = [];
  function walkDirs(dir) {
    if (!existsSync(dir)) return;
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      if (!entry.isDirectory()) continue;
      if (entry.name.startsWith('.') || entry.name === 'node_modules') continue;
      const full = join(dir, entry.name);
      allDirs.push({ name: entry.name, path: relative(MARKETING_ROOT, full).replace(/\\/g, '/') });
      walkDirs(full);
    }
  }
  walkDirs(SRC_APP);

  const routeGroups = allDirs.filter(d => /^\(.*\)$/.test(d.name));
  const parallelSlots = allDirs.filter(d => d.name.startsWith('@'));
  const intercepting = allDirs.filter(d => d.name === '(.)' || d.name === '(..)' || d.name === '(...)');

  console.log(`  Route groups found: ${routeGroups.length}${routeGroups.length > 0 ? ' — ' + routeGroups.map(d => d.path).join(', ') : ''}`);
  console.log(`  Parallel slots found: ${parallelSlots.length}${parallelSlots.length > 0 ? ' — ' + parallelSlots.map(d => d.path).join(', ') : ''}`);
  console.log(`  Intercepting routes found: ${intercepting.length}${intercepting.length > 0 ? ' — ' + intercepting.map(d => d.path).join(', ') : ''}`);

  // --- Dynamic route expansion ---
  console.log('\nDynamic Route Expansion:');
  console.log('------------------------');
  const dynamicRoutes = sourceRoutes.filter(r => r.is_dynamic);
  if (dynamicRoutes.length === 0) {
    console.log('  No dynamic routes found.');
  } else {
    for (const r of dynamicRoutes) {
      console.log(`  Pattern: ${r.resolved_url}`);
      // Try to read generateStaticParams from layout
      const layoutPath = join(SRC_APP, ...r.resolved_url.split('/').filter(Boolean).map(s => s), '..', 'layout.tsx');
      // Check out/ for concrete pages
      const outSubdir = join(OUT_DIR, ...r.resolved_url.split('/').filter(s => s && !s.startsWith('[') && !s.startsWith(':')));
      if (existsSync(outSubdir)) {
        const concreteFiles = readdirSync(outSubdir).filter(f => f.endsWith('.html'));
        console.log(`  Concrete pages in out/: ${concreteFiles.length}`);
        for (const f of concreteFiles) {
          const slug = f.replace('.html', '');
          const parentPath = r.resolved_url.replace(/\/\[.*\]$/, '');
          console.log(`    ${parentPath}/${slug}`);
        }
      }
    }
  }

  // --- Public static HTML ---
  console.log('\nPublic Static HTML (public/):');
  console.log('----------------------------');
  const publicHtml = findHtmlFiles(PUBLIC_DIR);
  if (publicHtml.length === 0) {
    console.log('  No HTML files found in public/');
  } else {
    for (const f of publicHtml) {
      const rel = relative(PUBLIC_DIR, f).replace(/\\/g, '/');
      console.log(`  /${rel}`);
    }
  }

  // --- Build output HTML ---
  console.log('\nBuild Output HTML (out/):');
  console.log('------------------------');
  const outHtml = findHtmlFiles(OUT_DIR);
  if (outHtml.length === 0) {
    console.log('  No HTML files found in out/ (run npm run build first)');
  } else {
    for (const f of outHtml) {
      const rel = relative(OUT_DIR, f).replace(/\\/g, '/');
      console.log(`  /${rel}`);
    }
  }

  // --- Missing SEO files ---
  console.log('\nSEO Infrastructure:');
  console.log('-------------------');
  const seoFiles = [
    { path: join(PUBLIC_DIR, 'robots.txt'), name: 'public/robots.txt' },
    { path: join(PUBLIC_DIR, 'sitemap.xml'), name: 'public/sitemap.xml' },
    { path: join(PUBLIC_DIR, 'llms.txt'), name: 'public/llms.txt' },
    { path: join(SRC_APP, 'sitemap.ts'), name: 'src/app/sitemap.ts' },
    { path: join(SRC_APP, 'robots.ts'), name: 'src/app/robots.ts' },
  ];
  for (const f of seoFiles) {
    const exists = existsSync(f.path);
    console.log(`  ${exists ? '✅' : '❌'} ${f.name}`);
  }

  // --- Route truth hierarchy (Gate C-D0.4) ---
  console.log('\nRoute Truth Hierarchy:');
  console.log('----------------------');
  const truth = collectRouteTruth(MARKETING_ROOT);
  const { data: registry } = loadRegistry(MARKETING_ROOT);
  const registryRoutes = registry.routes.flatMap((r) =>
    r.generated_concrete_routes?.length ? r.generated_concrete_routes : [r.logical_route]
  );

  console.log(`  source_intent_routes (${truth.source_intent_routes.length}):`);
  for (const r of truth.source_intent_routes) console.log(`    ${r}`);
  console.log(`  generated_content_instances (${truth.generated_content_instances.length}):`);
  for (const r of truth.generated_content_instances) console.log(`    ${r}`);
  console.log(`  exported_out_routes (${truth.exported_out_routes.length}):`);
  for (const r of truth.exported_out_routes) console.log(`    ${r}`);
  console.log(`  registry_routes (${registryRoutes.length}):`);
  for (const r of registryRoutes.slice(0, 15)) console.log(`    ${r}`);
  if (registryRoutes.length > 15) console.log(`    ... and ${registryRoutes.length - 15} more`);
  console.log(`  resolver_advisory_routes: same as source (${truth.resolver_advisory_routes.length}) — advisory only`);
  if (truth.unknown_or_ambiguous_routes.length) {
    console.log(`  unknown_or_ambiguous_routes (${truth.unknown_or_ambiguous_routes.length}):`);
    for (const u of truth.unknown_or_ambiguous_routes) console.log(`    ${JSON.stringify(u)}`);
  } else {
    console.log('  unknown_or_ambiguous_routes: none');
  }

  // --- Summary JSON ---
  const summary = {
    timestamp: new Date().toISOString(),
    route_truth_hierarchy: {
      source_intent_routes: truth.source_intent_routes,
      generated_content_instances: truth.generated_content_instances,
      exported_out_routes: truth.exported_out_routes,
      registry_routes: registryRoutes,
      resolver_advisory_routes: truth.resolver_advisory_routes,
      unknown_or_ambiguous_routes: truth.unknown_or_ambiguous_routes,
    },
    source_routes: sourceRoutes,
    app_router_conventions: {
      route_groups: routeGroups.length,
      parallel_slots: parallelSlots.length,
      intercepting_routes: intercepting.length,
      dynamic_segments: dynamicRoutes.length,
    },
    content_slugs: parseArticleSlugsFromContent(MARKETING_ROOT),
    public_html_count: publicHtml.length,
    build_output_html_count: outHtml.length,
    public_html: publicHtml.map(f => '/' + relative(PUBLIC_DIR, f).replace(/\\/g, '/')),
    build_output_html: outHtml.map(f => '/' + relative(OUT_DIR, f).replace(/\\/g, '/')),
  };

  console.log('\n=== Summary JSON ===');
  console.log(JSON.stringify(summary, null, 2));

  return summary;
}

main();
