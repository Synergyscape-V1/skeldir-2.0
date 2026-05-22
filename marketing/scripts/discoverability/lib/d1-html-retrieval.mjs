/**
 * D1 — HTML-first retrieval validators (static export truth).
 * Pure functions; no network (except harness caller may curl).
 */

import fs from 'node:fs';
import path from 'node:path';
import { readCrawlUrlAuthority } from './d2-crawl-graph.mjs';

/** @param {string} html */
export function stripScriptsAndStyles(html) {
  return html
    .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
    .replace(/<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>/gi, '');
}

/** Approximate visible text length after dropping scripts/styles/tags. */
export function visibleTextLength(html) {
  const s = stripScriptsAndStyles(html).replace(/<[^>]+>/g, ' ');
  return s.replace(/\s+/g, ' ').trim().length;
}

/** @param {string} html */
export function countSemanticHeadings(html) {
  const body = stripScriptsAndStyles(html);
  const m = body.match(/<h[23][\s>]/gi);
  return m ? m.length : 0;
}

/** Primary loading shell heuristic (D1 defect pattern). */
export function hasLoadingShell(html) {
  const lower = html.toLowerCase();
  if (lower.includes('animate-pulse') && lower.includes('loading')) return true;
  if (/>loading\.{3}</i.test(html) && visibleTextLength(html) < 800) return true;
  return false;
}

/**
 * @param {string} html — full page
 * @param {object} opts
 * @param {string} [opts.slug]
 * @returns {string[]} error messages (empty = pass)
 */
export function validateArticleHtml(html, opts = {}) {
  const errors = [];
  if (!html || html.length < 500) errors.push('article HTML too short or empty');

  if (!/<h1[\s>]/i.test(html)) errors.push('missing <h1>');

  const h23 = countSemanticHeadings(html);
  if (h23 < 3) errors.push(`expected at least 3 <h2>/<h3> in body, found ${h23}`);

  const textLen = visibleTextLength(html);
  if (textLen < 1000) errors.push(`expected at least 1000 characters of visible text, found ${textLen}`);

  if (hasLoadingShell(html)) errors.push('loading shell / animate-pulse placeholder detected');

  const body = stripScriptsAndStyles(html).toLowerCase();
  if (!/\d{4}-\d{2}-\d{2}/.test(html) && !/(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4}/i.test(html)) {
    errors.push('missing visible publish date (ISO or month year)');
  }

  if (!/application\/ld\+json/i.test(html)) {
    errors.push('missing application/ld+json in raw HTML');
  }

  if (!/by\s+/i.test(body) && !body.includes('amulya') && !body.includes('julie') && !body.includes('matt')) {
    errors.push('missing author marker in visible text');
  }

  return errors;
}

/**
 * @param {string} html
 * @param {string[]} expectedSlugs
 * @returns {string[]}
 */
export function validateResourcesHubAnchors(html, expectedSlugs) {
  const errors = [];
  const hrefRe = /href="(\/resources\/[^"]+)"/g;
  const hrefs = new Set();
  let m;
  while ((m = hrefRe.exec(html)) !== null) {
    hrefs.add(m[1].replace(/\/$/, ''));
  }
  for (const slug of expectedSlugs) {
    const path = `/resources/${slug}`;
    if (!hrefs.has(path)) {
      errors.push(`missing anchor href for ${path} in resources hub HTML`);
    }
  }
  return errors;
}

/**
 * @param {string} html
 * @returns {string[]}
 */
export function validateMarketingCommercialHtml(html) {
  const errors = [];
  if (!html || html.length < 400) errors.push('page HTML unexpectedly short');
  if (!/<h1[\s>]/i.test(html)) errors.push('missing <h1>');
  if (hasLoadingShell(html)) errors.push('loading shell detected on marketing route');
  const textLen = visibleTextLength(html);
  if (textLen < 400) errors.push(`insufficient visible text (${textLen} chars)`);
  return errors;
}

/**
 * Files that must not contain `"use client"` for D1 article document boundary.
 * @param {string} marketingRoot
 * @returns {string[]}
 */
export function forbiddenUseClientArticlePaths() {
  return [
    path.join('src', 'app', 'resources', '[slug]', 'page.tsx'),
    path.join('src', 'data', 'articleBodyRegistry.tsx'),
    path.join('src', 'components', 'article', 'ArticleContent.tsx'),
    path.join('src', 'components', 'article', 'ArticleContent2.tsx'),
    path.join('src', 'components', 'article', 'ArticleContent3.tsx'),
    path.join('src', 'components', 'article', 'ArticleContent4.tsx'),
    path.join('src', 'components', 'article', 'ArticleHeader.tsx'),
    path.join('src', 'components', 'article', 'TableOfContents.tsx'),
    path.join('src', 'components', 'article', 'RelatedArticles.tsx'),
    path.join('src', 'components', 'resources', 'ArticleCard.tsx'),
    path.join('src', 'components', 'resources', 'ArticleGrid.tsx'),
    path.join('src', 'components', 'resources', 'ResourcesHero.tsx'),
  ];
}

/**
 * @param {string} marketingRoot
 * @returns {string[]}
 */
export function validateNoUseClientOnArticleDocument(marketingRoot) {
  const errors = [];
  for (const rel of forbiddenUseClientArticlePaths()) {
    const full = path.join(marketingRoot, rel);
    if (!fs.existsSync(full)) {
      errors.push(`expected file missing: ${rel}`);
      continue;
    }
    const src = fs.readFileSync(full, 'utf8');
    if (src.includes('"use client"')) {
      errors.push(`forbidden "use client" in ${rel}`);
    }
  }
  return errors;
}

/** Next.js-style JSON-LD serialization for `<script type="application/ld+json">`. */
export function serializeJsonLdForScript(obj) {
  return JSON.stringify(obj).replace(/</g, '\\u003c');
}

/**
 * @param {string} html
 * @returns {string[]}
 */
export function extractJsonLdScriptInnerHtmls(html) {
  const re = /<script[^>]*type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi;
  const out = [];
  let m;
  while ((m = re.exec(html)) !== null) {
    out.push(m[1].trim());
  }
  return out;
}

/**
 * @param {string} html
 * @param {{ slug: string, title: string, excerpt: string, publishDate: string, author?: string }} meta
 * @returns {string[]}
 */
export function validateArticleJsonLdAgainstMetadata(html, meta) {
  const errors = [];
  const blocks = extractJsonLdScriptInnerHtmls(html);
  if (blocks.length === 0) {
    errors.push('no application/ld+json blocks found');
    return errors;
  }

  let articleLd = null;
  for (const raw of blocks) {
    if (/<(?![/!])/.test(raw)) {
      errors.push('JSON-LD script body contains raw "<" (expected \\u003c escaping)');
    }
    let o;
    try {
      o = JSON.parse(raw);
    } catch (e) {
      errors.push(`JSON-LD JSON.parse failed: ${e.message}`);
      continue;
    }
    const t = o['@type'];
    if (t === 'Article' || (Array.isArray(t) && t.includes('Article'))) {
      articleLd = o;
      break;
    }
  }

  if (!articleLd) {
    errors.push('no @type Article JSON-LD object found');
    return errors;
  }

  if (articleLd.headline !== meta.title) {
    errors.push(`JSON-LD headline mismatch: expected "${meta.title}", got "${articleLd.headline}"`);
  }
  if (articleLd.description !== meta.excerpt) {
    errors.push('JSON-LD description does not match articlesData excerpt');
  }
  if (articleLd.datePublished !== meta.publishDate || articleLd.dateModified !== meta.publishDate) {
    errors.push('JSON-LD dates do not match articlesData publishDate');
  }
  const expectedAuthor = meta.author || 'Amulya Puri';
  const an = articleLd.author && articleLd.author.name;
  if (an !== expectedAuthor) {
    errors.push(`JSON-LD author.name mismatch: expected "${expectedAuthor}", got "${an}"`);
  }
  const { SITE_ORIGIN } = readCrawlUrlAuthority(process.cwd());
  const expectedUrl = `${SITE_ORIGIN}/resources/${meta.slug}`;
  const pageId = articleLd.mainEntityOfPage && articleLd.mainEntityOfPage['@id'];
  const url = articleLd.url;
  if (pageId !== expectedUrl && url !== expectedUrl) {
    errors.push(`JSON-LD canonical URL mismatch: expected "${expectedUrl}" in url or mainEntityOfPage.@id`);
  }

  const serialized = serializeJsonLdForScript(articleLd);
  if (serialized.includes('<')) {
    errors.push('re-serialized Article JSON-LD still contains raw "<"');
  }

  return errors;
}

/**
 * Registry article routes in discoverability.routes.json must match articlesData slugs.
 * @param {object} registry
 * @param {string[]} slugs
 * @returns {string[]}
 */
export function validateRegistryArticleInstances(registry, slugs) {
  const errors = [];
  const routes = registry.routes || [];
  const articleRoutes = routes.filter((r) => r.route_type === 'article' && r.generated_concrete_routes?.length);
  const normalized = new Set();
  for (const r of articleRoutes) {
    for (const u of r.generated_concrete_routes) {
      const s = String(u);
      const pathOnly = s.startsWith('http') ? (() => {
        try {
          return new URL(s).pathname;
        } catch {
          return s;
        }
      })() : s;
      const clean = pathOnly.replace(/\/$/, '');
      const m = clean.match(/\/resources\/([^/]+)$/);
      if (m) normalized.add(m[1]);
    }
  }

  for (const slug of slugs) {
    if (!normalized.has(slug)) {
      errors.push(`registry missing article instance for slug: ${slug}`);
    }
  }
  for (const rs of normalized) {
    if (!slugs.includes(rs)) {
      errors.push(`registry has article instance not present in articlesData: ${rs}`);
    }
  }
  return errors;
}

/**
 * /book-demo must remain contained: not sitemap-implemented while still a candidate defect surface.
 * @param {object} registry
 * @returns {string[]}
 */
export function validateBookDemoSitemapContainment(registry) {
  const errors = [];
  const routes = registry.routes || [];
  const bd = routes.find((r) => r.logical_route === '/book-demo' || r.id === 'route-book-demo');
  if (!bd) {
    errors.push('registry: route-book-demo not found');
    return errors;
  }
  if (bd.sitemap_implemented === true && bd.status && bd.status.includes('defective')) {
    errors.push('/book-demo must not set sitemap_implemented=true while route remains defective');
  }
  if (bd.sitemap_required === true) {
    errors.push('/book-demo must keep sitemap_required=false until repair (D0 containment)');
  }
  return errors;
}
