/**
 * Parse article metadata objects from articlesData.ts without executing TS.
 * Relies on stable field order: slug, title, ... excerpt ... publishDate ... author (optional).
 */

import fs from 'node:fs';
import path from 'node:path';

/**
 * @param {string} marketingRoot
 * @returns {{ slug: string, title: string, excerpt: string, publishDate: string, author?: string }[]}
 */
export function parseArticlesMetadataFromSource(marketingRoot) {
  const file = path.join(marketingRoot, 'src', 'data', 'articlesData.ts');
  const src = fs.readFileSync(file, 'utf8');
  const out = [];

  // Match each article block starting at id: through the closing }; before next id or ];
  const blockRe =
    /\{\s*id:\s*'[^']+'\s*,\s*slug:\s*'([^']+)'\s*,\s*title:\s*'((?:\\'|[^'])*)'[\s\S]*?excerpt:\s*'((?:\\'|[^'])*)'[\s\S]*?publishDate:\s*'([^']+)'([\s\S]*?)\},/g;

  let m;
  while ((m = blockRe.exec(src)) !== null) {
    const slug = m[1];
    const title = m[2].replace(/\\'/g, "'");
    const excerpt = m[3].replace(/\\'/g, "'");
    const publishDate = m[4];
    const rest = m[5] || '';
    const am = /author:\s*'([^']*)'/.exec(rest);
    const author = am ? am[1] : undefined;
    out.push({ slug, title, excerpt, publishDate, author });
  }

  if (out.length === 0) {
    throw new Error('articles-metadata-from-source: parsed zero articles from articlesData.ts');
  }

  return out;
}
