/**
 * D6 — Evidence library architecture helpers (pure, no network).
 */

import fs from 'node:fs';
import path from 'node:path';
import { stripScriptsAndStyles, visibleTextLength, hasLoadingShell } from './d1-html-retrieval.mjs';

export const D6_D5_PROOF_HREFS = [
  '/methodology',
  '/revenue-verification',
  '/attribution-methodology',
  '/discrepancy-taxonomy',
  '/ai-boundary',
  '/trust-envelope',
  '/security',
  '/api',
  '/docs',
];

/** Minimum queries that must appear in the buyer-query matrix JSON. */
export const D6_REQUIRED_MATRIX_QUERIES = [
  'Why are Meta numbers higher than Stripe?',
  'Why do Google Ads and Shopify revenue disagree?',
  'How do I audit platform-reported revenue?',
  'How do I reconcile Shopify orders to ad-channel claims?',
  'What causes attribution discrepancies?',
  'How should finance validate ROAS before budget shifts?',
  'What does Skeldir mean by verified revenue?',
  'What is a TrustEnvelope?',
  'What is deterministic attribution?',
  'What is deterministic vs probabilistic confidence?',
  'What does AI explain versus calculate?',
  'What are the privacy/no-PII boundaries?',
  'What benchmark limitations apply?',
];

export const D6_REQUIRED_MATRIX_CATEGORIES = [
  'platform_discrepancy',
  'revenue_verification',
  'finance_audit',
  'attribution_methodology',
  'trust_envelope',
  'confidence_semantics',
  'privacy_boundary',
  'ai_boundary',
  'benchmark_methodology',
];

export const D6_CORE_EVIDENCE_ROUTES = [
  '/resources/evidence',
  '/resources/evidence/meta-vs-stripe',
  '/resources/evidence/google-ads-vs-shopify',
  '/resources/evidence/shopify-reconciliation',
  '/resources/evidence/finance-roas-audit-checklist',
  '/resources/evidence/deterministic-attribution-methods',
  '/resources/evidence/deterministic-vs-probabilistic-confidence',
  '/resources/evidence/benchmark-methodology',
  '/resources/evidence/privacy-no-pii-methodology',
  '/resources/evidence/trust-envelope-technical-spec',
  '/resources/evidence/ai-llm-explanation-boundary',
  '/resources/evidence/tiktok-discrepancies',
  '/resources/evidence/pinterest-discrepancies',
  '/resources/evidence/paypal-reconciliation',
  '/resources/evidence/woocommerce-reconciliation',
];

export const D6_PLATFORM_PAIR_ROUTES = [
  '/resources/evidence/meta-vs-stripe',
  '/resources/evidence/google-ads-vs-shopify',
];

export const D6_SECTION_HEADINGS = [
  'Bottom line',
  'Key Facts',
  'Claims and evidence',
  'Capability status',
  'How Skeldir Treats This',
  'Methodology',
  'What This Does Not Prove',
  'Limitations',
  'Related methodology pages',
  'Common questions',
  'Last Reviewed',
  'Owner',
];

export const D6_BANNED_OVERCLAIM_REGEXES = [
  /\bcross-tenant benchmark\b/i,
  /\bBayesian confidence is authoritative\b/i,
  /\bwe collect no PII\b/i,
  /\bwe collect zero PII\b/i,
  /\bsigned artifact\b/i,
  /\bauto-execute\b/i,
  /\bexternal alpha\b/i,
];

export const D6_LIVE_API_BANNED = /\blive API\b/i;

/**
 * @param {string} marketingRoot
 */
export function loadBuyerQueryMatrix(marketingRoot) {
  const p = path.join(marketingRoot, 'discoverability.buyer-query-matrix.json');
  if (!fs.existsSync(p)) throw new Error(`Missing ${p}`);
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}

/**
 * @param {string} marketingRoot
 */
export function loadEvidenceLibraryRegistry(marketingRoot) {
  const p = path.join(marketingRoot, 'discoverability.evidence-library-registry.json');
  if (!fs.existsSync(p)) throw new Error(`Missing ${p}`);
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}

/**
 * @param {string} marketingRoot
 */
export function loadSimilarityOverrides(marketingRoot) {
  const p = path.join(marketingRoot, 'discoverability.d6-similarity-overrides.json');
  if (!fs.existsSync(p)) return { pair_overrides: [] };
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}

/**
 * @param {string} html
 */
export function extractEvidenceTextForSimilarity(html) {
  const s = stripScriptsAndStyles(html);
  const noNav = s.replace(/<nav\b[\s\S]*?<\/nav>/gi, ' ');
  const noFooter = noNav.replace(/<footer\b[\s\S]*?<\/footer>/gi, ' ');
  const text = noFooter
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase();
  const boiler = new Set([
    'bluf',
    'key facts',
    'claim',
    'evidence',
    'methodology',
    'limitations',
    'last reviewed',
    'owner',
    'related proof pages',
    'related buyer questions',
    'how skeldir treats this',
    'what this does not prove',
    'capability status',
    'skeldir product engineering',
    'technical_disclosure_only',
    'quarterly',
    '90 days',
  ]);
  return text
    .split(/\W+/)
    .filter((w) => w.length > 2 && !boiler.has(w))
    .join(' ');
}

/**
 * @param {string} a
 * @param {string} b
 */
export function jaccardWordSimilarity(a, b) {
  const A = new Set(a.split(/\s+/).filter(Boolean));
  const B = new Set(b.split(/\s+/).filter(Boolean));
  if (A.size === 0 && B.size === 0) return 1;
  if (A.size === 0 || B.size === 0) return 0;
  let inter = 0;
  for (const x of A) {
    if (B.has(x)) inter++;
  }
  const union = A.size + B.size - inter;
  return union ? inter / union : 0;
}

/**
 * @param {string} marketingRoot
 * @param {string} logicalPath
 * @param {string} html
 * @returns {string[]}
 */
export function validateD6EvidenceDetailHtml(_marketingRoot, logicalPath, html) {
  const errors = [];
  if (!html || html.length < 800) errors.push(`${logicalPath}: HTML unexpectedly short`);
  if (!/<h1[\s>]/i.test(html)) errors.push(`${logicalPath}: missing <h1>`);
  if (visibleTextLength(html) < 1200) errors.push(`${logicalPath}: insufficient visible text for evidence page`);
  if (hasLoadingShell(html)) errors.push(`${logicalPath}: loading shell detected`);
  for (const h of D6_SECTION_HEADINGS) {
    if (!html.includes(h)) {
      errors.push(`${logicalPath}: missing required section heading "${h}"`);
    }
  }
  const lower = html.toLowerCase();
  let proofHit = false;
  for (const href of D6_D5_PROOF_HREFS) {
    if (lower.includes(`href="${href}"`) || lower.includes(`href='${href}'`)) {
      proofHit = true;
      break;
    }
  }
  if (!proofHit) {
    errors.push(`${logicalPath}: missing anchor href to at least one methodology page`);
  }
  if (!lower.includes('capability status')) {
    errors.push(`${logicalPath}: missing capability status block heading`);
  }
  for (const re of D6_BANNED_OVERCLAIM_REGEXES) {
    if (re.test(html)) errors.push(`${logicalPath}: banned overclaim phrase matched ${re}`);
  }
  if (D6_LIVE_API_BANNED.test(html)) {
    const ok = /unavailable|planned|not described as|not asserted|not claimed/i.test(html);
    if (!ok) {
      errors.push(
        `${logicalPath}: contains "live API" wording — add explicit unavailable/planned/not-described-as-live capability language`,
      );
    }
  }
  return errors;
}

/**
 * @param {string} _marketingRoot
 * @param {string} html
 */
export function validateD6EvidenceHubHtml(_marketingRoot, html) {
  const errors = [];
  if (!html || html.length < 600) errors.push('/resources/evidence: HTML unexpectedly short');
  if (!/<h1[\s>]/i.test(html)) errors.push('/resources/evidence: missing <h1>');
  if (hasLoadingShell(html)) errors.push('/resources/evidence: loading shell');
  const must = [
    'Evidence Library',
    'Revenue Verification',
    'Platform Discrepancies',
    'Finance Audit',
    'TrustEnvelope',
    'Benchmark Methodology',
  ];
  for (const m of must) {
    if (!html.includes(m)) errors.push(`/resources/evidence: missing cluster marker "${m}"`);
  }
  for (const href of D6_D5_PROOF_HREFS.slice(0, 3)) {
    if (!html.includes(`href="${href}"`)) {
      errors.push(`/resources/evidence: missing link to ${href}`);
    }
  }
  return errors;
}

/**
 * @param {object} matrix
 * @returns {string[]}
 */
export function validateBuyerQueryMatrixShape(matrix) {
  const errors = [];
  if (!matrix || matrix.version === undefined) errors.push('buyer-query-matrix: missing version');
  const entries = matrix.entries;
  if (!Array.isArray(entries)) errors.push('buyer-query-matrix: entries must be array');
  if (!entries) return errors;
  const requiredFields = [
    'query',
    'query_category',
    'buyer_role',
    'search_intent',
    'agent_retrieval_intent',
    'canonical_route',
    'route_status',
    'proof_routes',
    'claim_registry_refs',
    'priority',
    'owner',
    'last_reviewed',
  ];
  const cats = new Set();
  for (const e of entries) {
    for (const f of requiredFields) {
      if (!(f in e)) errors.push(`buyer-query-matrix: entry missing "${f}" for query "${e.query || ''}"`);
    }
    if (e.query_category) cats.add(e.query_category);
  }
  for (const q of D6_REQUIRED_MATRIX_QUERIES) {
    if (!entries.some((entry) => entry.query === q)) {
      errors.push(`buyer-query-matrix: missing required query "${q}"`);
    }
  }
  for (const c of D6_REQUIRED_MATRIX_CATEGORIES) {
    if (!cats.has(c)) errors.push(`buyer-query-matrix: missing category "${c}"`);
  }
  return errors;
}

/**
 * @param {object} reg
 * @returns {string[]}
 */
/**
 * All-pairs Jaccard similarity for evidence detail routes (hub excluded).
 * @param {string} marketingRoot
 * @param {(route: string) => string | null} readHtml
 * @param {string[]} routes
 * @param {{ hard?: number, soft?: number }} [thresholds]
 */
export function computeEvidenceAllPairsSimilarity(
  marketingRoot,
  readHtml,
  routes,
  thresholds = {},
) {
  const hard = thresholds.hard ?? 0.85;
  const soft = thresholds.soft ?? 0.72;
  const detailRoutes = routes.filter((r) => r !== '/resources/evidence');
  const texts = new Map();
  for (const route of detailRoutes) {
    const html = readHtml(route);
    texts.set(route, html ? extractEvidenceTextForSimilarity(html) : '');
  }
  const overrides = loadSimilarityOverrides(marketingRoot).pair_overrides || [];
  const rows = [];
  const errors = [];
  for (let i = 0; i < detailRoutes.length; i++) {
    for (let j = i + 1; j < detailRoutes.length; j++) {
      const routeA = detailRoutes[i];
      const routeB = detailRoutes[j];
      const ta = texts.get(routeA) || '';
      const tb = texts.get(routeB) || '';
      const score = jaccardWordSimilarity(ta, tb);
      const pairKey = `${routeA.replace('/resources/evidence/', '')}|${routeB.replace('/resources/evidence/', '')}`;
      const manualOverride = overrides.some((o) => o.pair === pairKey && o.justification);
      let result = 'pass';
      if (score >= hard && !manualOverride) {
        result = 'fail';
        errors.push(
          `${routeA} × ${routeB}: similarity ${score.toFixed(3)} >= hard ${hard} without manual override`,
        );
      } else if (score >= soft) {
        result = 'warn';
      }
      rows.push({
        routeA,
        routeB,
        similarityScore: Number(score.toFixed(4)),
        threshold: score >= hard ? hard : soft,
        result,
        manualOverride: Boolean(manualOverride),
      });
    }
  }
  return { rows, errors };
}

export function validateEvidenceLibraryRegistryShape(reg) {
  const errors = [];
  if (!reg || reg.version === undefined) errors.push('evidence-library-registry: missing version');
  const pages = reg.pages;
  if (!Array.isArray(pages)) errors.push('evidence-library-registry: pages must be array');
  if (!pages) return errors;
  const fields = [
    'route',
    'cluster',
    'primary_query',
    'secondary_queries',
    'proof_authority_routes',
    'content_status',
    'indexable',
    'sitemap_required',
    'schema_type',
    'owner',
    'last_reviewed',
    'similarity_group',
  ];
  for (const p of pages) {
    for (const f of fields) {
      if (!(f in p)) errors.push(`evidence-library-registry: page missing "${f}" for ${p.route || '?'}`);
    }
  }
  return errors;
}
