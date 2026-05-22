/**
 * D2 — crawl graph, sitemap, robots, canonical, and internal link hygiene (pure helpers).
 * D2-C2 — URL authority read from `src/lib/crawlUrls.ts`; static sitemap/robots contract checks.
 */

import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { parseArticleSlugsFromContent, slugToArticleRoute } from './content-slugs.mjs';

/**
 * Read `SITE_ORIGIN` / `TRAILING_SLASH` from the TypeScript URL authority (single source of truth).
 * @param {string} marketingRoot
 */
export function readCrawlUrlAuthority(marketingRoot) {
  const tsPath = path.join(marketingRoot, 'src', 'lib', 'crawlUrls.ts');
  if (!fs.existsSync(tsPath)) {
    throw new Error(`Missing crawl URL authority module: ${tsPath}`);
  }
  const src = fs.readFileSync(tsPath, 'utf8');
  const originM = /export const SITE_ORIGIN\s*=\s*["']([^"']+)["']/.exec(src);
  if (!originM) throw new Error(`SITE_ORIGIN not found in ${tsPath}`);
  const slashM = /export const TRAILING_SLASH\b[^=]*=\s*(true|false)/.exec(src);
  const SITE_ORIGIN = originM[1].replace(/\/$/, '');
  return {
    SITE_ORIGIN,
    TRAILING_SLASH: slashM ? slashM[1] === 'true' : false,
  };
}

/** @param {string} s */
function escapeRegExp(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * @param {object} auth from readCrawlUrlAuthority
 */
export function robotsSitemapLineFromAuthority(auth) {
  return `Sitemap: ${auth.SITE_ORIGIN}/sitemap.xml`;
}

/**
 * @param {string} marketingRoot
 * @returns {string[]}
 */
export function validateManifestOriginMatchesAuthority(marketingRoot) {
  const errors = [];
  const auth = readCrawlUrlAuthority(marketingRoot);
  const manifestPath = path.join(marketingRoot, 'discoverability.sitemap-manifest.json');
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  if (manifest.origin && manifest.origin !== auth.SITE_ORIGIN) {
    errors.push(
      `discoverability.sitemap-manifest.json origin "${manifest.origin}" must equal crawlUrls SITE_ORIGIN "${auth.SITE_ORIGIN}"`,
    );
  }
  return errors;
}

/**
 * @param {string} content
 * @param {string} [label]
 * @returns {string[]}
 */
export function validateSitemapSourceStringStaticSafe(content, label = 'sitemap.ts') {
  const errors = [];
  if (
    !/export\s+const\s+dynamic\s*=\s*["']error["']/.test(content) &&
    !/export\s+const\s+dynamic\s*=\s*["']force-static["']/.test(content)
  ) {
    errors.push(`${label} must export const dynamic = "error" or "force-static" (D2-C2 static contract)`);
  }
  const banned = [
    [/from\s*["']next\/headers["']/, 'next/headers'],
    [/\bcookies\s*\(/, 'cookies()'],
    [/\bheaders\s*\(/, 'headers()'],
    [/\bdraftMode\s*\(/, 'draftMode()'],
    [/\bconnection\s*\(/, 'connection()'],
    [/\bunstable_/, 'unstable_*'],
    [/cache:\s*["']no-store["']/, "cache: 'no-store'"],
    [/\bDate\.now\s*\(/, 'Date.now'],
  ];
  for (const [re, name] of banned) {
    if (re.test(content)) errors.push(`${label} must not use ${name} (static export guard)`);
  }
  if (/https:\/\/skeldir\.com/i.test(content)) {
    errors.push(`${label} must not embed literal https://skeldir.com — import from @/lib/crawlUrls`);
  }
  return errors;
}

/**
 * @param {string} marketingRoot
 * @returns {string[]}
 */
export function validateSitemapSourceStaticSafe(marketingRoot) {
  const p = path.join(marketingRoot, 'src', 'app', 'sitemap.ts');
  const s = fs.readFileSync(p, 'utf8');
  return validateSitemapSourceStringStaticSafe(s, 'sitemap.ts');
}

/**
 * @param {string} content
 * @param {string} [label]
 * @returns {string[]}
 */
export function validateRobotsSourceStringStaticAndNoLiteralOrigin(content, label = 'robots.ts') {
  const errors = [];
  if (!/export\s+const\s+dynamic\s*=\s*["']error["']/.test(content)) {
    errors.push(`${label} must export const dynamic = "error" (D2-C2 static contract)`);
  }
  if (/https:\/\/skeldir\.com/i.test(content)) {
    errors.push(`${label} must not embed literal https://skeldir.com — use robotsSitemapUrl() from @/lib/crawlUrls`);
  }
  return errors;
}

/**
 * @param {string} marketingRoot
 * @returns {string[]}
 */
export function validateRobotsSourceStaticAndNoLiteralOrigin(marketingRoot) {
  const p = path.join(marketingRoot, 'src', 'app', 'robots.ts');
  const s = fs.readFileSync(p, 'utf8');
  return validateRobotsSourceStringStaticAndNoLiteralOrigin(s, 'robots.ts');
}

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
  const auth = readCrawlUrlAuthority(marketingRoot);
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  if (manifest.origin && manifest.origin !== auth.SITE_ORIGIN) {
    throw new Error(`manifest.origin "${manifest.origin}" !== crawlUrls SITE_ORIGIN "${auth.SITE_ORIGIN}"`);
  }
  const origin = auth.SITE_ORIGIN.replace(/\/$/, '');
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
 * @param {string} [marketingRoot]
 * @returns {string[]}
 */
export function validateSitemapXmlWellFormed(xml, marketingRoot = process.cwd()) {
  const errors = [];
  if (!xml || xml.length < 50) errors.push('sitemap XML missing or too small');
  if (!/<urlset[\s\S]+xmlns=["']http:\/\/www\.sitemaps\.org\/schemas\/sitemap\/0\.9["']/.test(xml)) {
    errors.push('sitemap missing urlset with sitemap 0.9 xmlns');
  }
  if (!/<loc>/.test(xml)) errors.push('sitemap has no <loc> entries');
  const locs = parseSitemapLocs(xml);
  if (locs.length === 0) errors.push('parsed zero sitemap locs');
  const auth = readCrawlUrlAuthority(marketingRoot);
  const host = new URL(`${auth.SITE_ORIGIN}/`).hostname;
  const escapedHost = escapeRegExp(host);
  const locPattern = new RegExp(`^https://${escapedHost}(/[\\w./-]*)?$`, 'i');
  const locPatternRoot = new RegExp(`^https://${escapedHost}/$`, 'i');
  for (const loc of locs) {
    if (!locPattern.test(loc) && !locPatternRoot.test(loc)) {
      errors.push(`sitemap loc not under ${auth.SITE_ORIGIN}: ${loc}`);
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
 * Non-root sitemap URLs must not end with `/` when TRAILING_SLASH is false (matches crawlUrls contract).
 * @param {string[]} locs
 * @param {string} marketingRoot
 */
export function validateSitemapLocPathsNoTrailingSlashExceptRoot(locs, marketingRoot) {
  const errors = [];
  const { TRAILING_SLASH } = readCrawlUrlAuthority(marketingRoot);
  if (TRAILING_SLASH) return errors;
  for (const loc of locs) {
    let pathname;
    try {
      pathname = new URL(loc).pathname;
    } catch {
      errors.push(`invalid sitemap loc URL: ${loc}`);
      continue;
    }
    if (pathname !== '/' && pathname.endsWith('/')) {
      errors.push(`sitemap loc must not use trailing slash on non-root path (D2-C2): ${loc}`);
    }
  }
  return errors;
}

/**
 * @param {string} locUrl
 * @param {string} canonicalHref
 * @returns {string[]}
 */
export function validateSitemapLocCanonicalPathAlignment(locUrl, canonicalHref) {
  const errors = [];
  let lp;
  let cp;
  try {
    lp = new URL(locUrl).pathname;
    cp = new URL(canonicalHref).pathname;
  } catch (e) {
    errors.push(`invalid URL in loc/canonical alignment: ${e}`);
    return errors;
  }
  const norm = (p) => {
    if (p.length > 1 && p.endsWith('/')) return p.slice(0, -1);
    return p;
  };
  if (norm(lp) !== norm(cp)) {
    errors.push(`canonical path does not match sitemap loc path: loc=${lp} canonical=${cp}`);
  }
  const locTrail = lp !== '/' && lp.endsWith('/');
  const canTrail = cp !== '/' && cp.endsWith('/');
  if (locTrail !== canTrail) {
    errors.push(`trailing slash mismatch between sitemap loc and canonical: ${locUrl} vs ${canonicalHref}`);
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
  errors.push(...validateSitemapLocPathsNoTrailingSlashExceptRoot(actual, marketingRoot));
  return errors;
}

/**
 * @param {string} body
 * @param {string} [marketingRoot]
 */
export function validateRobotsPolicy(body, marketingRoot = process.cwd()) {
  const errors = [];
  if (!body || body.length < 20) errors.push('robots.txt empty');
  const auth = readCrawlUrlAuthority(marketingRoot);
  const expectedRe = new RegExp(`sitemap:\\s*${escapeRegExp(auth.SITE_ORIGIN)}/sitemap\\.xml`, 'i');
  if (!expectedRe.test(body)) {
    errors.push(`robots.txt missing Sitemap: ${auth.SITE_ORIGIN}/sitemap.xml`);
  }
  let wildcardStarHasBlanketDisallow = false;
  let inWildcardStarGroup = false;
  for (const raw of body.split(/\r?\n/)) {
    const line = raw.trim();
    if (/^user-agent:\s*\*/i.test(line)) {
      inWildcardStarGroup = true;
      continue;
    }
    if (/^user-agent:/i.test(line)) {
      inWildcardStarGroup = false;
      continue;
    }
    if (inWildcardStarGroup && /^\s*disallow:\s*\/\s*$/i.test(line)) {
      wildcardStarHasBlanketDisallow = true;
      break;
    }
  }
  if (wildcardStarHasBlanketDisallow && !/^\s*#\s*disallow:\s*\//im.test(body)) {
    errors.push('robots.txt wildcard User-agent: * contains blanket Disallow: /');
  }
  const sensitive = ['/node_modules', '/.git', '/src/', '.env', 'package.json', 'C:\\', 'C:/'];
  for (const s of sensitive) {
    if (body.includes(s)) errors.push(`robots.txt leaks sensitive fragment: ${s}`);
  }
  if (/user-agent:\s*\*/i.test(body)) {
    if (/disallow:\s*\/product/i.test(body)) errors.push('robots blocks /product for public crawlers');
    if (/disallow:\s*\/resources/i.test(body)) errors.push('robots blocks /resources for public crawlers');
  }
  if (/disallow:\s*\/book-demo/i.test(body)) {
    errors.push(
      'robots.txt must not Disallow /book-demo when index exclusion uses HTML noindex (crawlers cannot observe noindex if blocked)',
    );
  }
  if (/disallow:\s*\/implementations/i.test(body)) {
    errors.push(
      'robots.txt must not Disallow /implementations/ for deindexing while claiming HTML noindex proof — pick crawlable noindex or remove public artifacts (D2-C)',
    );
  }
  return errors;
}

/**
 * @param {string} body
 * @param {string} marketingRoot
 */
export function validateRobotsSitemapUrlMatchesAuthority(body, marketingRoot) {
  const errors = [];
  const auth = readCrawlUrlAuthority(marketingRoot);
  const m = /sitemap:\s*(\S+)/i.exec(body);
  if (!m) return errors;
  const found = m[1].trim();
  const expected = `${auth.SITE_ORIGIN}/sitemap.xml`;
  if (found !== expected) {
    errors.push(`robots Sitemap URL "${found}" !== crawl authority "${expected}" (D2-C2)`);
  }
  return errors;
}

/**
 * Parse Disallow path values from the first `User-agent: *` block (case-insensitive).
 * @param {string} body
 * @returns {string[]}
 */
export function parseRobotsDisallowPaths(body) {
  const lines = body.split(/\r?\n/);
  const disallows = [];
  let inStar = false;
  for (const raw of lines) {
    const line = raw.trim();
    if (/^user-agent:\s*\*/i.test(line)) {
      inStar = true;
      continue;
    }
    if (/^user-agent:/i.test(line)) {
      inStar = false;
      continue;
    }
    if (!inStar) continue;
    const m = /^disallow:\s*(.+)$/i.exec(line);
    if (!m) continue;
    const val = m[1].trim();
    if (val && val !== '/') disallows.push(val);
  }
  return disallows;
}

/**
 * If HTML uses meta noindex for index exclusion, robots.txt must not block that URL for * crawlers.
 * @param {string} robotsBody
 * @param {string[]} pathnames — e.g. ['/Login','/book-demo']
 */
export function validateRobotsDoesNotBlockMetaNoindexRoutes(robotsBody, pathnames) {
  const errors = [];
  const disallows = parseRobotsDisallowPaths(robotsBody);
  for (const pathname of pathnames) {
    const p = pathname.startsWith('/') ? pathname : `/${pathname}`;
    for (const d of disallows) {
      const dNorm = d.split(/\s+/)[0].trim();
      if (!dNorm) continue;
      const prefix = dNorm.endsWith('/') ? dNorm.slice(0, -1) : dNorm;
      if (p === prefix || p.startsWith(`${prefix}/`)) {
        errors.push(
          `robots Disallow "${dNorm}" blocks "${p}" which uses meta noindex — crawlers cannot fetch and cannot observe noindex (D2-C crawlability law)`,
        );
      }
    }
  }
  return errors;
}

/**
 * Routes that ship meta noindex in static HTML (must remain crawlable; never pair with robots Disallow).
 */
export const META_NOINDEX_PUBLIC_PATHS = [
  '/Login',
  '/signup',
  '/book-demo',
  '/book-demo/thank-you',
  '/privacy',
  '/terms',
  '/gdpr',
  '/security',
  '/status',
  '/about',
  '/careers',
  '/press',
  '/docs',
  '/api',
  '/trust-envelope',
];

/**
 * @param {string} html
 */
export function htmlHasNoindexFollow(html) {
  const re = /<meta[^>]*name=["']robots["'][^>]*content=["']([^"']+)["']/gi;
  let m;
  while ((m = re.exec(html)) !== null) {
    const c = m[1].toLowerCase();
    if (c.includes('noindex') && !c.includes('nofollow')) return true;
  }
  return false;
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
 * /book-demo while registry-marked defective must not rely on sitemap exclusion alone (D2-C).
 * @param {object} registry
 * @param {string} bookDemoHtml
 * @returns {string[]}
 */
export function validateBookDemoDefectiveRequiresNoindex(registry, bookDemoHtml) {
  const errors = [];
  const bd = registry.routes?.find((r) => r.id === 'route-book-demo');
  if (!bd) {
    errors.push('registry missing route-book-demo');
    return errors;
  }
  const defective = bd.status && String(bd.status).includes('defective');
  if (!defective) return errors;
  if (!htmlHasNoindexRobots(bookDemoHtml)) {
    errors.push('/book-demo is registry-defective but static HTML lacks noindex (sitemap exclusion is not index exclusion)');
  }
  if (!htmlHasNoindexFollow(bookDemoHtml)) {
    errors.push('/book-demo must emit noindex,follow (crawlable deindexing) while defective — avoid nofollow-only');
  }
  return errors;
}

/**
 * D2-C2: defective contained /book-demo must not emit self-canonical unless registry documents an exception.
 * @param {object} registry
 * @param {string} bookDemoHtml
 * @returns {string[]}
 */
export function validateBookDemoDefectiveNoSelfCanonical(registry, bookDemoHtml) {
  const errors = [];
  const bd = registry.routes?.find((r) => r.id === 'route-book-demo');
  if (!bd) {
    errors.push('registry missing route-book-demo');
    return errors;
  }
  const defective = bd.status && String(bd.status).includes('defective');
  if (!defective) return errors;
  const exc = bd.canonical_exception_justification;
  if (exc && String(exc).trim()) return errors;
  const cans = extractCanonicalHrefs(bookDemoHtml);
  if (cans.length > 0) {
    errors.push(
      'D2-C2: /book-demo is defective+noindexed but HTML still emits rel=canonical — remove canonical or set canonical_exception_justification in registry',
    );
  }
  return errors;
}

/**
 * If review artifacts ship under `out/implementations/`, each must carry crawlable noindex (strategy B).
 * Strategy A (preferred): directory absent — then this returns [].
 * @param {string} outDir — marketing `out/` root
 * @returns {string[]}
 */
export function validateShippedImplementationAgentsHaveNoindex(outDir) {
  const errors = [];
  const implDir = path.join(outDir, 'implementations');
  if (!fs.existsSync(implDir)) return errors;
  const agents = ['agent-a', 'agent-b', 'agent-c', 'agent-d', 'agent-e'];
  for (const ag of agents) {
    const p = path.join(implDir, ag, 'index.html');
    if (!fs.existsSync(p)) continue;
    const h = fs.readFileSync(p, 'utf8');
    if (!htmlHasNoindexRobots(h)) {
      errors.push(`/implementations/${ag}/ present in export but lacks noindex meta (D2-C)`);
    }
  }
  return errors;
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
  if (process.env.GITHUB_ACTIONS === 'true' || process.env.CI === 'true') return [];
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
