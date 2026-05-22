/**
 * D2 — crawl graph, sitemap, robots, canonical, and internal link hygiene (pure helpers).
 */

import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { parseArticleSlugsFromContent, slugToArticleRoute } from './content-slugs.mjs';

const SITE_ORIGIN = 'https://skeldir.com';

/** @param {string} xml */
export function parseSitemapLocs(xml) {
  const locs = [];
  const re = /<loc>\s*([^<]+?)<\/loc>/gi;
  let m;
  while ((m = re.exec(xml)) !== null) {
    locs.push(m[1].trim());
  }
  return locs;
}

/**
 * Expected absolute sitemap URLs for Phase D2 (registry-aligned indexable marketing surface).
 * @param {string} marketingRoot
 * @returns {string[]}
 */
export function getExpectedSitemapUrls(marketingRoot) {
  const manifestPath = path.join(marketingRoot, 'discoverability.sitemap-manifest.json');
  if (!fs.existsSync(manifestPath)) {
    throw new Error(`Missing ${manifestPath}`);
  }
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  const origin = (manifest.origin || SITE_ORIGIN).replace(/\/$/, '');
  const staticPaths = manifest.staticPaths || [];
  const slugs = parseArticleSlugsFromContent(marketingRoot);
  const urls = [];
  for (const p of staticPaths) {
    const u = p === '/' ? `${origin}/` : `${origin}${p}`;
    urls.push(u);
  }
  for (const slug of slugs) {
    urls.push(`${origin}${slugToArticleRoute(slug)}`);
  }
  return urls;
}

/**
 * @param {string} xml
 * @returns {string[]}
 */
export function validateSitemapXmlWellFormed(xml) {
  const errors = [];
  if (!xml || xml.length < 50) errors.push('sitemap XML missing or too small');
  if (!/<urlset[\s\S]+xmlns=["']http:\/\/www\.sitemaps\.org\/schemas\/sitemap\/0\.9["']/.test(xml)) {
    errors.push('sitemap missing urlset with sitemap 0.9 xmlns');
  }
  if (!/<loc>/.test(xml)) errors.push('sitemap has no <loc> entries');
  const locs = parseSitemapLocs(xml);
  if (locs.length === 0) errors.push('parsed zero sitemap locs');
  for (const loc of locs) {
    if (!/^https:\/\/skeldir\.com(\/[\w\-./]*)?$/.test(loc) && !/^https:\/\/skeldir\.com\/$/.test(loc)) {
      errors.push(`sitemap loc not under skeldir.com: ${loc}`);
    }
    if (loc.includes('utm_')) errors.push(`sitemap loc contains tracking params: ${loc}`);
  }
  const lastmods = (xml.match(/<lastmod>/gi) || []).length;
  if (lastmods < locs.length) {
    errors.push('expected a <lastmod> per <url> entry for deterministic freshness signals');
  }
  return errors;
}

/**
 * @param {string} marketingRoot
 * @param {string[]} locs
 * @returns {string[]}
 */
export function validateSitemapMatchesExpected(marketingRoot, locs) {
  const errors = [];
  const actual = [...new Set(locs.map((u) => u.trim()))];
  const expected = getExpectedSitemapUrls(marketingRoot);
  const actualSet = new Set(actual);
  const expectedSet = new Set(expected);
  if (actualSet.size !== expectedSet.size) {
    errors.push(`sitemap url count ${actualSet.size} !== expected ${expectedSet.size}`);
  }
  for (const e of expectedSet) {
    if (!actualSet.has(e)) errors.push(`sitemap missing expected URL: ${e}`);
  }
  for (const a of actualSet) {
    if (!expectedSet.has(a)) errors.push(`sitemap contains unexpected URL: ${a}`);
  }

  const forbiddenExact = new Set([
    '/Login',
    '/login',
    '/signup',
    '/book-demo',
    '/book-demo/thank-you',
    '/404',
    '/_not-found',
    '/privacy',
    '/security',
    '/docs',
    '/api',
    '/trust-envelope',
    '/status',
    '/about',
    '/careers',
    '/press',
    '/terms',
    '/gdpr',
  ]);

  for (const loc of actual) {
    let pathOnly;
    try {
      pathOnly = new URL(loc).pathname.replace(/\/$/, '') || '/';
    } catch {
      errors.push(`invalid sitemap loc URL: ${loc}`);
      continue;
    }
    if (forbiddenExact.has(pathOnly)) {
      errors.push(`forbidden sitemap URL (non-indexable or placeholder): ${loc}`);
    }
    if (pathOnly.startsWith('/implementations')) {
      errors.push(`forbidden sitemap URL (review artifact): ${loc}`);
    }
  }
  return errors;
}

/**
 * @param {string} body
 */
export function validateRobotsPolicy(body) {
  const errors = [];
  if (!body || body.length < 20) errors.push('robots.txt empty');
  if (!/sitemap:\s*https:\/\/skeldir\.com\/sitemap\.xml/i.test(body)) {
    errors.push('robots.txt missing Sitemap: https://skeldir.com/sitemap.xml');
  }
  if (/^\s*disallow:\s*\/\s*$/im.test(body) && !/^\s*#\s*disallow:\s*\//im.test(body)) {
    errors.push('robots.txt contains blanket Disallow: /');
  }
  const sensitive = ['/node_modules', '/.git', '/src/', '.env', 'package.json', 'C:\\', 'C:/'];
  for (const s of sensitive) {
    if (body.includes(s)) errors.push(`robots.txt leaks sensitive fragment: ${s}`);
  }
  if (/user-agent:\s*\*/i.test(body)) {
    if (/disallow:\s*\/product/i.test(body)) errors.push('robots blocks /product for public crawlers');
    if (/disallow:\s*\/resources/i.test(body)) errors.push('robots blocks /resources for public crawlers');
  }
  return errors;
}

/**
 * @param {string} html
 * @returns {string[]}
 */
export function extractCanonicalHrefs(html) {
  const out = [];
  const re = /<link[^>]*rel=["']canonical["'][^>]*href=["']([^"']+)["'][^>]*>/gi;
  let m;
  while ((m = re.exec(html)) !== null) out.push(m[1].trim());
  const re2 = /<link[^>]*href=["']([^"']+)["'][^>]*rel=["']canonical["'][^>]*>/gi;
  while ((m = re2.exec(html)) !== null) out.push(m[1].trim());
  return [...new Set(out)];
}

/**
 * @param {string} pathname — e.g. /product
 * @returns {string|null} relative path under out/
 */
export function sitemapPathToOutRelative(pathname) {
  const p = pathname === '/' || pathname === '' ? '/' : pathname.startsWith('/') ? pathname : `/${pathname}`;
  if (p === '/') return 'index.html';
  if (p.startsWith('/resources/')) {
    const slug = p.slice('/resources/'.length).replace(/\/$/, '');
    if (!slug) return null;
    return `resources/${slug}.html`;
  }
  const clean = p.replace(/^\//, '').replace(/\/$/, '');
  if (!clean) return 'index.html';
  return `${clean}.html`;
}

/**
 * @param {string} html
 * @returns {boolean}
 */
export function htmlHasNoindexRobots(html) {
  return /<meta[^>]*name=["']robots["'][^>]*content=["'][^"']*noindex/i.test(html);
}

/**
 * @param {string} html
 * @param {string} label
 */
export function footerLabelHref(html, label) {
  const esc = label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const re = new RegExp(`<a[^>]*href="([^"]+)"[^>]*>\\s*${esc}\\s*<`, 'i');
  const m = re.exec(html);
  if (!m) return null;
  return m[1];
}

/**
 * @param {string} html
 * @returns {string[]}
 */
export function validateFooterLegalAndSupportHygiene(html) {
  const errors = [];
  const privacy = footerLabelHref(html, 'Privacy Policy');
  if (privacy === '/resources') errors.push('Privacy Policy still links to /resources');
  if (privacy && privacy !== '/privacy') errors.push(`Privacy Policy href unexpected: ${privacy}`);

  const api = footerLabelHref(html, 'API Reference');
  if (api === '/resources') errors.push('API Reference still links to /resources');
  if (api && api !== '/api') errors.push(`API Reference href unexpected: ${api}`);

  const docs = footerLabelHref(html, 'Documentation');
  if (docs === '/resources') errors.push('Documentation still links to /resources');
  if (docs && docs !== '/docs') errors.push(`Documentation href unexpected: ${docs}`);

  if (/href="\/resources"[^>]*>\s*Terms of Service/i.test(html)) {
    errors.push('Terms of Service still links to /resources');
  }
  if (/href="\/resources"[^>]*>\s*GDPR/i.test(html)) {
    errors.push('GDPR still links to /resources');
  }
  return errors;
}

/**
 * @param {string} marketingRoot
 * @returns {string[]}
 */
export function assertDiscoverabilityGitBranchPolicy(marketingRoot) {
  if (process.env.D2_SKIP_BRANCH_CHECK === '1') return [];
  const candidates = [path.join(marketingRoot, '.git'), path.join(marketingRoot, '..', '.git')];
  const hasGit = candidates.some((p) => fs.existsSync(p));
  if (!hasGit) return [];
  const r = spawnSync('git', ['rev-parse', '--abbrev-ref', 'HEAD'], {
    cwd: marketingRoot,
    encoding: 'utf8',
  });
  if (r.status !== 0) return ['git rev-parse --abbrev-ref HEAD failed (set D2_SKIP_BRANCH_CHECK=1 to skip)'];
  const branch = (r.stdout || '').trim();
  if (branch === 'master' || branch === 'main') {
    return [
      `D2 git policy: on branch "${branch}" — use isolated feature branch feat/discoverability-remediation (set D2_SKIP_BRANCH_CHECK=1 only for CI smoke where intentional).`,
    ];
  }
  return [];
}
