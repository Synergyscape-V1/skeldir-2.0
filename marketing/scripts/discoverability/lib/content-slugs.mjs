import fs from 'node:fs';
import path from 'node:path';

/**
 * Parse article slugs from articlesData.ts without executing TypeScript.
 * Source of truth for generated article instances.
 * @param {string} marketingRoot
 * @returns {string[]}
 */
export function parseArticleSlugsFromContent(marketingRoot) {
  const file = path.join(marketingRoot, 'src', 'data', 'articlesData.ts');
  if (!fs.existsSync(file)) {
    throw new Error(`Article content source not found: ${file}`);
  }
  const content = fs.readFileSync(file, 'utf8');
  const slugs = [];
  const re = /slug:\s*['"]([^'"]+)['"]/g;
  let match;
  while ((match = re.exec(content)) !== null) {
    slugs.push(match[1]);
  }
  return slugs;
}

/**
 * @param {string} slug
 * @returns {string}
 */
export function slugToArticleRoute(slug) {
  return `/resources/${slug}`;
}

/**
 * @param {string[]} slugs
 * @returns {string[]}
 */
export function slugsToArticleRoutes(slugs) {
  return slugs.map(slugToArticleRoute);
}
