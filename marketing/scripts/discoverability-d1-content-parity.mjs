#!/usr/bin/env node

/**
 * D1 — Content source / routing parity (no full build).
 * Use after edits: validates articlesData ↔ body registry ↔ TOC ↔ generateStaticParams source.
 */

import {
  validateArticleBodyRegistrySourceParity,
  validateTocSlugSourceParity,
  validateGenerateStaticParamsUsesArticles,
} from './discoverability/lib/d1-article-source-parity.mjs';

const MARKETING_ROOT = process.cwd();
let failures = 0;

function fail(m) {
  console.error(`  ❌ FAIL: ${m}`);
  failures++;
}

function pass(m) {
  console.log(`  ✅ PASS: ${m}`);
}

function main() {
  console.log('╔══════════════════════════════════════════════╗');
  console.log('║  Skeldir D1 — Content parity (source scan)     ║');
  console.log('╚══════════════════════════════════════════════╝\n');

  const a = validateArticleBodyRegistrySourceParity(MARKETING_ROOT);
  if (a.length) a.forEach(fail);
  else pass('articleBodyRegistry.tsx ↔ articlesData slugs');

  const b = validateTocSlugSourceParity(MARKETING_ROOT);
  if (b.length) b.forEach(fail);
  else pass('TableOfContents ARTICLE_TOC_GENERATORS ↔ articlesData slugs');

  const c = validateGenerateStaticParamsUsesArticles(MARKETING_ROOT);
  if (c.length) c.forEach(fail);
  else pass('[slug]/layout generateStaticParams uses articles.map');

  console.log(`\nFailures: ${failures}`);
  if (failures) process.exit(1);
}

main();
