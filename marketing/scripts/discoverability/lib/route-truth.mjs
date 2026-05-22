import fs from 'node:fs';
import path from 'node:path';
import { resolvePagePathToRoutePattern } from './app-router-resolve.mjs';
import { parseArticleSlugsFromContent, slugsToArticleRoutes } from './content-slugs.mjs';

export const ROUTE_TRUTH_HIERARCHY = [
  'out_build_artifacts',
  'next_build_artifacts',
  'content_generateStaticParams',
  'source_route_scan',
  'app_router_resolver_advisory',
];

/**
 * @param {string} dir
 * @param {string[]} results
 */
function findPageFiles(dir, results = []) {
  if (!fs.existsSync(dir)) return results;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name.startsWith('.') || entry.name === 'node_modules') continue;
      findPageFiles(full, results);
    } else if (/^page\.(tsx|ts|jsx|js)$/.test(entry.name)) {
      results.push(full);
    }
  }
  return results;
}

/**
 * @param {string} dir
 * @param {string[]} results
 */
function findHtmlFiles(dir, results = []) {
  if (!fs.existsSync(dir)) return results;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name.startsWith('.') || entry.name === 'node_modules' || entry.name === '_next') continue;
      findHtmlFiles(full, results);
    } else if (entry.name.endsWith('.html')) {
      results.push(full);
    }
  }
  return results;
}

/**
 * @param {string} marketingRoot
 * @param {string} pageFilePath
 */
export function sourcePageToRoute(marketingRoot, pageFilePath) {
  const srcApp = path.join(marketingRoot, 'src', 'app');
  const rel = path.relative(srcApp, path.dirname(pageFilePath)).replace(/\\/g, '/');
  if (!rel || rel === '.') return '/';
  const { routePattern } = resolvePagePathToRoutePattern(
    rel === '' ? 'page.tsx' : `${rel}/page.tsx`
  );
  return routePattern;
}

/**
 * @param {string} marketingRoot
 * @param {string} htmlPath
 */
export function outHtmlToRoute(marketingRoot, htmlPath) {
  const outDir = path.join(marketingRoot, 'out');
  const rel = path.relative(outDir, htmlPath).replace(/\\/g, '/');
  if (rel === 'index.html') return '/';
  if (rel.endsWith('.html')) {
    const withoutExt = rel.slice(0, -'.html'.length);
    return withoutExt ? `/${withoutExt}` : '/';
  }
  if (rel.endsWith('/index.html')) {
    const without = rel.slice(0, -'/index.html'.length);
    return without ? `/${without}` : '/';
  }
  return null;
}

/**
 * @param {string} marketingRoot
 */
export function collectRouteTruth(marketingRoot) {
  const srcApp = path.join(marketingRoot, 'src', 'app');
  const publicDir = path.join(marketingRoot, 'public');
  const outDir = path.join(marketingRoot, 'out');

  const sourcePages = findPageFiles(srcApp);
  const sourceIntentRoutes = sourcePages.map((fp) => sourcePageToRoute(marketingRoot, fp)).sort();
  const resolverAdvisoryRoutes = sourcePages
    .map((fp) => {
      const rel = path.relative(srcApp, path.dirname(fp)).replace(/\\/g, '/');
      const input = rel ? `${rel}/page.tsx` : 'page.tsx';
      return resolvePagePathToRoutePattern(input).routePattern;
    })
    .sort();

  const contentSlugs = parseArticleSlugsFromContent(marketingRoot);
  const generatedContentInstances = slugsToArticleRoutes(contentSlugs).sort();

  const exportedOutRoutes = [];
  if (fs.existsSync(outDir)) {
    for (const fp of findHtmlFiles(outDir)) {
      const route = outHtmlToRoute(marketingRoot, fp);
      if (route && !route.startsWith('/_not-found')) {
        exportedOutRoutes.push(route);
      }
    }
  }
  exportedOutRoutes.sort();

  const publicStaticRoutes = [];
  for (const fp of findHtmlFiles(publicDir)) {
    const rel = path.relative(publicDir, fp).replace(/\\/g, '/');
    if (rel.endsWith('/index.html')) {
      const route = outHtmlToRoute(marketingRoot, path.join(outDir, rel));
      if (route) publicStaticRoutes.push(route);
    }
  }
  publicStaticRoutes.sort();

  const unknownOrAmbiguous = [];
  for (let i = 0; i < sourceIntentRoutes.length; i++) {
    if (sourceIntentRoutes[i] !== resolverAdvisoryRoutes[i]) {
      unknownOrAmbiguous.push({
        type: 'resolver_disagreement',
        source: sourceIntentRoutes[i],
        resolver: resolverAdvisoryRoutes[i],
      });
    }
  }

  return {
    source_intent_routes: sourceIntentRoutes,
    resolver_advisory_routes: resolverAdvisoryRoutes,
    generated_content_instances: generatedContentInstances,
    exported_out_routes: exportedOutRoutes,
    public_static_routes: publicStaticRoutes,
    unknown_or_ambiguous_routes: unknownOrAmbiguous,
    content_slugs: contentSlugs,
  };
}

/**
 * Normalize route for set comparisons.
 * @param {string} route
 */
export function normalizeRoute(route) {
  if (!route) return '/';
  const trimmed = route.replace(/\/$/, '') || '/';
  return trimmed;
}

/**
 * @param {string} marketingRoot
 */
export function discoverArticleOutRoutes(marketingRoot) {
  const outDir = path.join(marketingRoot, 'out', 'resources');
  if (!fs.existsSync(outDir)) return [];
  return fs
    .readdirSync(outDir)
    .filter((name) => name.endsWith('.html'))
    .map((name) => `/resources/${name.replace(/\.html$/, '')}`)
    .sort();
}
