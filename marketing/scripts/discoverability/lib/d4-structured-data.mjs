/**
 * D4 — structured data (JSON-LD) validation helpers.
 */

import fs from 'node:fs';
import path from 'node:path';
import { extractJsonLdScriptInnerHtmls } from './d1-html-retrieval.mjs';
import { htmlHasNoindexRobots, META_NOINDEX_PUBLIC_PATHS, readCrawlUrlAuthority } from './d2-crawl-graph.mjs';

const RICH_FORBIDDEN_ON_NOINDEX = new Set([
  'Article',
  'SoftwareApplication',
  'Product',
  'CollectionPage',
  'TechArticle',
  'FinancialProduct',
]);

const JSON_LD_SCRIPT_BLOCK_RE = /<script[^>]*type=["']application\/ld\+json["'][^>]*>[\s\S]*?<\/script>/gi;

/**
 * @param {string} marketingRoot
 * @returns {{ sameAs: string[], waiverActive: boolean, waiver?: Record<string, unknown> }}
 */
export function loadEntityProfileRegistry(marketingRoot) {
  const p = path.join(marketingRoot, 'entity-profile-registry.json');
  if (!fs.existsSync(p)) {
    throw new Error(`Missing entity-profile-registry.json at ${p}`);
  }
  const j = JSON.parse(fs.readFileSync(p, 'utf8'));
  const arr = j.sameAs;
  if (!Array.isArray(arr)) throw new Error('entity-profile-registry.json must contain sameAs array');
  const waiver = j.entityAuthorityWaiver;
  const waiverActive = !!(waiver && waiver.active === true);
  return { sameAs: arr.map(String), waiverActive, waiver };
}

/**
 * @param {string} marketingRoot
 */
export function loadVerifiedSameAsUrls(marketingRoot) {
  return loadEntityProfileRegistry(marketingRoot).sameAs;
}

/**
 * @param {string} html
 * @returns {{ tag: string, start: number, end: number }[]}
 */
export function extractJsonLdScriptTagBlocks(html) {
  return [...html.matchAll(JSON_LD_SCRIPT_BLOCK_RE)].map((m) => ({
    tag: m[0],
    start: m.index,
    end: m.index + m[0].length,
  }));
}

/**
 * D4-C2: required JSON-LD must be wholly inside `<head>` (static export post-process relocates body scripts).
 * @param {string} html
 * @returns {string[]}
 */
export function validateJsonLdScriptsInHead(html) {
  const errors = [];
  const headClose = html.search(/<\/head>/i);
  if (headClose === -1) {
    errors.push('HTML missing </head> (cannot validate JSON-LD placement)');
    return errors;
  }
  for (const { start, end } of extractJsonLdScriptTagBlocks(html)) {
    const whollyInHead = start < headClose && end <= headClose;
    if (!whollyInHead) {
      errors.push(
        `JSON-LD script must be wholly inside <head> (script bytes ${start}-${end}, </head> starts at ${headClose})`,
      );
    }
  }
  return errors;
}

/**
 * @param {string} outDir
 * @returns {string[]}
 */
export function walkHtmlFiles(outDir) {
  const files = [];
  /** @param {string} d */
  function walk(d) {
    if (!fs.existsSync(d)) return;
    for (const ent of fs.readdirSync(d, { withFileTypes: true })) {
      const p = path.join(d, ent.name);
      if (ent.isDirectory()) walk(p);
      else if (ent.name.endsWith('.html')) files.push(p);
    }
  }
  walk(outDir);
  return files;
}

/**
 * @param {string} marketingRoot
 * @param {string} absHtmlPath
 */
export function outHtmlToLogicalPath(marketingRoot, absHtmlPath) {
  const rel = path.relative(path.join(marketingRoot, 'out'), absHtmlPath).replace(/\\/g, '/');
  if (rel === 'index.html') return '/';
  if (rel.startsWith('resources/') && rel.endsWith('.html')) {
    const slug = rel.slice('resources/'.length, -'.html'.length);
    return `/resources/${slug}`;
  }
  const base = rel.endsWith('.html') ? rel.slice(0, -'.html'.length) : rel;
  return `/${base}`;
}

/**
 * @param {string} html
 * @returns {object[]}
 */
export function parseAllJsonLdObjects(html) {
  const inners = extractJsonLdScriptInnerHtmls(html);
  const out = [];
  for (const raw of inners) {
    if (/<(?![/!])/.test(raw)) {
      throw new Error('JSON-LD contains raw "<" (expected \\u003c escaping)');
    }
    try {
      out.push(JSON.parse(raw));
    } catch (e) {
      throw new Error(`JSON-LD JSON.parse failed: ${e.message}`);
    }
  }
  return out;
}

/** @param {unknown} o */
function typesOfNode(o) {
  if (!o || typeof o !== 'object') return [];
  const t = /** @type {Record<string, unknown>} */ (o)['@type'];
  if (typeof t === 'string') return [t];
  if (Array.isArray(t)) return t.filter((x) => typeof x === 'string');
  return [];
}

/** @param {object[]} objs */
function findByType(objs, type) {
  return objs.filter((o) => typesOfNode(o).includes(type));
}

/**
 * @param {string} s
 */
function decodeBasicHtmlEntities(s) {
  return String(s)
    .replace(/&apos;/g, "'")
    .replace(/&#39;/g, "'")
    .replace(/&#x27;/gi, "'")
    .replace(/&quot;/g, '"')
    .replace(/&#34;/g, '"')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>');
}

/**
 * @param {string} s
 */
export function normalizeVisibleText(s) {
  return decodeBasicHtmlEntities(s).replace(/\u2019/g, "'").replace(/\u201c|\u201d/g, '"').trim();
}

/**
 * @param {string} html
 */
export function extractCanonicalHref(html) {
  const m = /<link[^>]*rel=["']canonical["'][^>]*href=["']([^"']+)["']/i.exec(html);
  return m ? m[1].trim() : null;
}

/**
 * @param {string} html
 */
export function extractMetaDescription(html) {
  const m =
    /<meta[^>]*name=["']description["'][^>]*content=["']([^"']*)["']/i.exec(html) ||
    /<meta[^>]*content=["']([^"']*)["'][^>]*name=["']description["']/i.exec(html);
  return m ? normalizeVisibleText(m[1]) : null;
}

/**
 * @param {string} html
 */
export function extractTitle(html) {
  const m = /<title[^>]*>([^<]*)<\/title>/i.exec(html);
  return m ? normalizeVisibleText(m[1]) : null;
}

/**
 * Prefer first h1 aria-label (double-quoted); else strip tags from first h1 body.
 * @param {string} html
 */
export function extractPrimaryH1Text(html) {
  const mdq = /<h1\b[^>]*\baria-label="([^"]*)"/i.exec(html);
  if (mdq) return normalizeVisibleText(mdq[1]);
  const m2 = /<h1\b[^>]*>([\s\S]*?)<\/h1>/i.exec(html);
  if (!m2) return null;
  return normalizeVisibleText(m2[1].replace(/<[^>]+>/g, '').replace(/\s+/g, ' '));
}

/**
 * @param {string} marketingRoot
 * @param {string} logicalPath e.g. /resources/foo
 * @param {string} html
 * @param {string[]} verifiedSameAs
 */
export function validateD4IndexablePage(marketingRoot, logicalPath, html, verifiedSameAs) {
  const errors = [];
  const auth = readCrawlUrlAuthority(marketingRoot);
  const origin = auth.SITE_ORIGIN;
  const expectedCanonical =
    logicalPath === '/' ? `${origin}/` : `${origin}${logicalPath.startsWith('/') ? logicalPath : `/${logicalPath}`}`;

  let objs;
  try {
    objs = parseAllJsonLdObjects(html);
  } catch (e) {
    errors.push(e.message);
    return errors;
  }

  const ch = extractCanonicalHref(html);
  if (ch) {
    const isRoot = logicalPath === '/';
    const rootOk = isRoot && (ch === `${origin}/` || ch === origin);
    if (!rootOk && ch !== expectedCanonical) {
      errors.push(`canonical mismatch: expected ${expectedCanonical}, got ${ch}`);
    }
  }

  const forbid = new Set(META_NOINDEX_PUBLIC_PATHS);
  const isNoindexSurface = forbid.has(logicalPath);
  const noindexHtml = htmlHasNoindexRobots(html);

  if (isNoindexSurface || noindexHtml) {
    for (const o of objs) {
      for (const t of typesOfNode(o)) {
        if (RICH_FORBIDDEN_ON_NOINDEX.has(t)) {
          errors.push(`forbidden rich @type ${t} on noindex/defective surface ${logicalPath}`);
        }
      }
    }
    return errors;
  }

  errors.push(...validateJsonLdScriptsInHead(html));

  const primaryH1 = extractPrimaryH1Text(html);
  if (!primaryH1) {
    errors.push(`${logicalPath}: indexable route must expose a primary <h1> (or h1 aria-label) in raw HTML`);
  }

  if (logicalPath === '/') {
    const org = findByType(objs, 'Organization')[0];
    const site = findByType(objs, 'WebSite')[0];
    const wp = findByType(objs, 'WebPage')[0];
    if (!org) errors.push('homepage: missing Organization JSON-LD');
    if (!site) errors.push('homepage: missing WebSite JSON-LD');
    if (!wp) errors.push('homepage: missing WebPage JSON-LD');
    if (org) {
      if (org['@id'] !== `${origin}/#organization`) errors.push(`Organization @id must be ${origin}/#organization`);
      if (org.url && !String(org.url).startsWith(origin)) errors.push('Organization.url must use SITE_ORIGIN');
      const sa = org.sameAs;
      if (Array.isArray(sa)) {
        for (const u of sa) {
          if (!verifiedSameAs.includes(u)) {
            errors.push(`Organization.sameAs URL not in entity-profile-registry: ${u}`);
          }
        }
      }
      const desc = String(org.description || '');
      if (!/deterministic revenue-verification|deterministic revenue verification/i.test(desc)) {
        errors.push('Organization.description must reflect canonical deterministic revenue-verification positioning');
      }
    }
    if (site && site['@id'] !== `${origin}/#website`) errors.push(`WebSite @id must be ${origin}/#website`);
    if (site && site.publisher && site.publisher['@id'] !== `${origin}/#organization`) {
      errors.push('WebSite.publisher.@id must reference organization @id');
    }
    if (wp && wp.name && !html.includes(String(wp.name))) {
      errors.push('homepage: WebPage.name must appear in raw HTML (match hero aria-label / H1)');
    }
    const metaD = extractMetaDescription(html);
    if (wp && metaD && normalizeVisibleText(String(wp.description || '')) !== normalizeVisibleText(metaD)) {
      errors.push('homepage: WebPage.description must match meta description');
    }
    if (site && metaD && site.description && normalizeVisibleText(String(site.description)) !== normalizeVisibleText(metaD)) {
      errors.push('homepage: WebSite.description must match meta description');
    }
    const normUrl = (u) => String(u).replace(/\/$/, '') || String(u);
    if (wp && ch && normUrl(String(wp.url)) !== normUrl(ch)) {
      errors.push(`homepage: WebPage.url must match canonical (got ${String(wp.url)}, canonical ${ch})`);
    }
  }

  if (logicalPath === '/product') {
    const app = findByType(objs, 'SoftwareApplication')[0];
    const wp = findByType(objs, 'WebPage')[0];
    if (!app) errors.push('/product: missing SoftwareApplication');
    if (!wp) errors.push('/product: missing WebPage');
    if (app && app.url && !String(app.url).startsWith(origin)) errors.push('SoftwareApplication.url must use SITE_ORIGIN');
    const h1 = extractPrimaryH1Text(html);
    if (app && h1 && app.alternateName && normalizeVisibleText(String(app.alternateName)) !== h1) {
      errors.push('/product: SoftwareApplication.alternateName must match visible H1');
    }
    const metaD = extractMetaDescription(html);
    if (app && metaD && normalizeVisibleText(String(app.description || '')) !== normalizeVisibleText(metaD)) {
      errors.push('/product: SoftwareApplication.description must match meta description');
    }
    const title = extractTitle(html);
    if (wp && title && wp.name && normalizeVisibleText(String(wp.name)) !== normalizeVisibleText(title)) {
      errors.push('/product: WebPage.name must match <title>');
    }
    if (wp && ch && String(wp.url) !== ch) errors.push('/product: WebPage.url must match canonical');
    if (app && ch && String(app.url) !== ch) errors.push('/product: SoftwareApplication.url must match canonical');
  }

  if (logicalPath === '/pricing' || logicalPath === '/agencies') {
    const wp = findByType(objs, 'WebPage')[0];
    if (!wp) errors.push(`${logicalPath}: missing WebPage JSON-LD`);
    if (findByType(objs, 'Offer').length) {
      errors.push(`${logicalPath}: unexpected top-level Offer JSON-LD`);
    }
    const h1 = extractPrimaryH1Text(html);
    if (wp && wp.name && h1 && normalizeVisibleText(String(wp.name)) !== h1) {
      errors.push(`${logicalPath}: WebPage.name must match visible H1`);
    }
    const metaD = extractMetaDescription(html);
    if (wp && metaD && normalizeVisibleText(String(wp.description || '')) !== normalizeVisibleText(metaD)) {
      errors.push(`${logicalPath}: WebPage.description must match meta description`);
    }
    if (wp && ch && String(wp.url) !== ch) {
      errors.push(`${logicalPath}: WebPage.url must match canonical`);
    }
  }

  if (logicalPath === '/resources') {
    const cp = findByType(objs, 'CollectionPage')[0];
    const bc = findByType(objs, 'BreadcrumbList')[0];
    if (!cp) errors.push('/resources: missing CollectionPage');
    if (!bc) errors.push('/resources: missing BreadcrumbList');
    const h1 = extractPrimaryH1Text(html);
    if (cp && cp.name && h1 && normalizeVisibleText(String(cp.name)) !== h1) {
      errors.push('/resources: CollectionPage.name must match visible H1');
    }
    const metaD = extractMetaDescription(html);
    if (cp && metaD && normalizeVisibleText(String(cp.description || '')) !== normalizeVisibleText(metaD)) {
      errors.push('/resources: CollectionPage.description must match meta description');
    }
    if (cp && ch && String(cp.url) !== ch) {
      errors.push('/resources: CollectionPage.url must match canonical');
    }
  }

  /** D6 evidence library hub — CollectionPage (not Article). */
  if (logicalPath === '/resources/evidence') {
    const cp = findByType(objs, 'CollectionPage')[0];
    const bc = findByType(objs, 'BreadcrumbList')[0];
    if (!cp) errors.push('/resources/evidence: missing CollectionPage');
    if (!bc) errors.push('/resources/evidence: missing BreadcrumbList');
    const h1 = extractPrimaryH1Text(html);
    if (cp && cp.name && h1 && normalizeVisibleText(String(cp.name)) !== h1) {
      errors.push('/resources/evidence: CollectionPage.name must match visible H1');
    }
    const metaD = extractMetaDescription(html);
    if (cp && metaD && normalizeVisibleText(String(cp.description || '')) !== normalizeVisibleText(metaD)) {
      errors.push('/resources/evidence: CollectionPage.description must match meta description');
    }
    if (cp && ch && String(cp.url) !== ch) {
      errors.push('/resources/evidence: CollectionPage.url must match canonical');
    }
  }

  /**
   * D6 evidence detail pages — conservative WebPage + BreadcrumbList
   * (avoid Article overclaim on query-addressed evidence surfaces).
   */
  if (logicalPath.startsWith('/resources/evidence/') && logicalPath !== '/resources/evidence') {
    const wp = findByType(objs, 'WebPage')[0];
    const bc = findByType(objs, 'BreadcrumbList')[0];
    if (!wp) errors.push(`${logicalPath}: missing WebPage JSON-LD`);
    if (!bc) errors.push(`${logicalPath}: missing BreadcrumbList`);
    const h1 = extractPrimaryH1Text(html);
    if (wp && wp.name && h1 && normalizeVisibleText(String(wp.name)) !== h1) {
      errors.push(`${logicalPath}: WebPage.name must match visible H1`);
    }
    const metaD = extractMetaDescription(html);
    if (wp && metaD && normalizeVisibleText(String(wp.description || '')) !== normalizeVisibleText(metaD)) {
      errors.push(`${logicalPath}: WebPage.description must match meta description`);
    }
    if (wp && ch && String(wp.url) !== ch) {
      errors.push(`${logicalPath}: WebPage.url must match canonical`);
    }
    if (bc && Array.isArray(bc.itemListElement)) {
      const last = bc.itemListElement[bc.itemListElement.length - 1];
      const item = last && last.item;
      if (item !== expectedCanonical) {
        errors.push(`${logicalPath}: BreadcrumbList last item must equal evidence page canonical`);
      }
    }
  }

  if (
    logicalPath.startsWith('/resources/') &&
    logicalPath !== '/resources' &&
    logicalPath !== '/resources/evidence' &&
    !logicalPath.startsWith('/resources/evidence/')
  ) {
    const art = findByType(objs, 'Article')[0];
    const bc = findByType(objs, 'BreadcrumbList')[0];
    if (!art) errors.push(`${logicalPath}: missing Article JSON-LD`);
    if (!bc) errors.push(`${logicalPath}: missing BreadcrumbList`);
    if (art) {
      if (!art.headline) errors.push(`${logicalPath}: Article missing headline`);
      if (!art.datePublished) errors.push(`${logicalPath}: Article missing datePublished`);
      const u = art.url;
      if (u !== expectedCanonical) {
        errors.push(`${logicalPath}: Article.url must match canonical (${expectedCanonical})`);
      }
      const me = art.mainEntityOfPage;
      const meId = me && typeof me === 'object' ? me['@id'] : null;
      if (meId && !String(meId).startsWith(expectedCanonical)) {
        errors.push(`${logicalPath}: Article.mainEntityOfPage.@id must be on-article URL`);
      }
      const h1 = extractPrimaryH1Text(html);
      const hn = h1 ? normalizeVisibleText(h1) : null;
      const headlineN = normalizeVisibleText(String(art.headline));
      if (hn && headlineN !== hn) {
        errors.push(`${logicalPath}: Article.headline must match visible H1`);
      }
      const title = extractTitle(html);
      if (title && art.headline && !title.startsWith(headlineN)) {
        errors.push(`${logicalPath}: HTML title should start with Article headline`);
      }
      const metaD = extractMetaDescription(html);
      if (metaD && art.description) {
        const descN = normalizeVisibleText(String(art.description));
        const metaN = normalizeVisibleText(metaD);
        if (descN !== metaN) {
          errors.push(`${logicalPath}: meta description should align with Article JSON-LD description`);
        }
      }
    }
    if (bc && Array.isArray(bc.itemListElement)) {
      const last = bc.itemListElement[bc.itemListElement.length - 1];
      const item = last && last.item;
      if (item !== expectedCanonical) {
        errors.push(`${logicalPath}: BreadcrumbList last item must equal article canonical`);
      }
    }
  }

  return errors;
}

/**
 * Every Organization node with an @id must use the canonical organization id.
 * @param {string} marketingRoot
 */
export function validateAllOrganizationIds(marketingRoot) {
  const errors = [];
  const auth = readCrawlUrlAuthority(marketingRoot);
  const expectedOrg = `${auth.SITE_ORIGIN}/#organization`;
  const outRoot = path.join(marketingRoot, 'out');
  for (const abs of walkHtmlFiles(outRoot)) {
    const html = fs.readFileSync(abs, 'utf8');
    let objs;
    try {
      objs = parseAllJsonLdObjects(html);
    } catch {
      continue;
    }
    for (const o of objs) {
      if (typesOfNode(o).includes('Organization') && o['@id'] && String(o['@id']) !== expectedOrg) {
        errors.push(`Organization @id ${o['@id']} must equal ${expectedOrg} (${abs})`);
      }
    }
  }
  return errors;
}

export function assertHtmlContainsUnescapedJsonLdLt(html) {
  const inners = extractJsonLdScriptInnerHtmls(html);
  for (const raw of inners) {
    if (raw.includes('<') && !raw.includes('\\u003c')) {
      return ['JSON-LD block contains unsafe raw "<" (expected \\\\u003c escaping)'];
    }
  }
  return [];
}
