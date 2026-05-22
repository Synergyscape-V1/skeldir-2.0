/**
 * D1 article source parity: articlesData ↔ body registry ↔ TOC map ↔ generateStaticParams.
 */

import fs from 'node:fs';
import path from 'node:path';
import { parseArticleSlugsFromContent } from './content-slugs.mjs';

/**
 * @param {string} marketingRoot
 * @returns {string[]}
 */
export function validateArticleBodyRegistrySourceParity(marketingRoot) {
  const errors = [];
  const slugs = parseArticleSlugsFromContent(marketingRoot);
  const regPath = path.join(marketingRoot, 'src', 'data', 'articleBodyRegistry.tsx');
  if (!fs.existsSync(regPath)) {
    errors.push('articleBodyRegistry.tsx missing');
    return errors;
  }
  const regSrc = fs.readFileSync(regPath, 'utf8');
  const regStart = regSrc.indexOf('export const articleBodyRegistry');
  const regEnd = regSrc.indexOf('assertArticleBodyRegistryParity', regStart);
  const regChunk = regEnd > regStart ? regSrc.slice(regStart, regEnd) : regSrc;

  for (const slug of slugs) {
    const escaped = slug.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const keyPat = new RegExp(`['"]${escaped}['"]\\s*:\\s*ArticleContent\\w*`);
    if (!keyPat.test(regChunk)) {
      errors.push(`articleBodyRegistry.tsx missing body mapping for slug: ${slug}`);
    }
  }

  const regKeys = new Set(
    [...regChunk.matchAll(/\n\s*['"]([a-z0-9-]+)['"]\s*:\s*ArticleContent\w*\s*,?/g)].map((x) => x[1])
  );
  const slugSet = new Set(slugs);
  for (const k of regKeys) {
    if (!slugSet.has(k)) {
      errors.push(`articleBodyRegistry.tsx has stale or unknown slug key: ${k}`);
    }
  }
  return errors;
}

/**
 * TOC keys inside getTOCItemsBySlug tocMap must match articlesData slugs.
 * @param {string} marketingRoot
 * @returns {string[]}
 */
export function validateTocSlugSourceParity(marketingRoot) {
  const errors = [];
  const slugs = parseArticleSlugsFromContent(marketingRoot);
  const tocPath = path.join(marketingRoot, 'src', 'components', 'article', 'TableOfContents.tsx');
  const src = fs.readFileSync(tocPath, 'utf8');
  const mapStart = src.indexOf('const ARTICLE_TOC_GENERATORS');
  if (mapStart === -1) {
    errors.push('TableOfContents.tsx: ARTICLE_TOC_GENERATORS not found');
    return errors;
  }
  const slice = src.slice(mapStart, mapStart + 2500);
  for (const slug of slugs) {
    const escaped = slug.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    if (!new RegExp(`['"]${escaped}['"]\\s*:`).test(slice)) {
      errors.push(`TableOfContents tocMap missing slug: ${slug}`);
    }
  }
  return errors;
}

/**
 * generateStaticParams in [slug]/layout must use articles.map(article => article.slug).
 * @param {string} marketingRoot
 * @returns {string[]}
 */
export function validateGenerateStaticParamsUsesArticles(marketingRoot) {
  const errors = [];
  const layoutPath = path.join(marketingRoot, 'src', 'app', 'resources', '[slug]', 'layout.tsx');
  const src = fs.readFileSync(layoutPath, 'utf8');
  if (!src.includes('generateStaticParams')) {
    errors.push('[slug]/layout.tsx missing generateStaticParams');
  }
  if (!/articles\.map\s*\(\s*\(?\s*article\s*\)?\s*=>\s*\(\s*\{\s*slug:\s*article\.slug/.test(src)) {
    errors.push(
      'generateStaticParams must derive slugs from articlesData via articles.map((article) => ({ slug: article.slug }))'
    );
  }
  return errors;
}
