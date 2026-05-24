/**
 * D5 — Trust Proof Boundary and Legal/Security Surface validation helpers.
 *
 * Pure helpers consumed by:
 *   - scripts/discoverability-d5-harness.mjs
 *   - scripts/discoverability-d5-negative-controls.mjs
 *
 * D5 splits the trust-proof surface into two zones:
 *
 *   1) Indexable proof surfaces — public, static, retrievable, must contain
 *      the concepts they claim. These are scanned for static H1, primary
 *      body, required concept sections, last-reviewed metadata, and
 *      canonical alignment. They must NOT be noindex.
 *
 *   2) Legal placeholder surfaces — `/privacy`, `/terms`, `/gdpr`. These
 *      remain noindex while legal review is pending. They must NOT invent
 *      legal guarantees (no SOC 2 / GDPR-compliant / encrypted-everywhere
 *      claims). They must carry an explicit review_status string in their
 *      static HTML so a skeptical reviewer sees the legal_review_required
 *      state on the page itself.
 *
 * No legal/security/compliance claims may be invented. See
 *   D5_BANNED_UNAPPROVED_PHRASES below.
 */

import fs from 'node:fs';
import path from 'node:path';
import {
  extractCanonicalHref,
  extractMetaDescription,
  extractPrimaryH1Text,
  extractTitle,
  normalizeVisibleText,
} from './d4-structured-data.mjs';
import {
  htmlHasNoindexRobots,
  readCrawlUrlAuthority,
} from './d2-crawl-graph.mjs';

/**
 * Indexable D5 proof surfaces. These MUST exist as static HTML, MUST be
 * indexable, MUST contain the concepts the marketing site asserts, and
 * MUST carry a visible last-reviewed token.
 */
export const D5_INDEXABLE_PROOF_ROUTES = [
  '/methodology',
  '/ai-boundary',
  '/trust-envelope',
  '/revenue-verification',
  '/attribution-methodology',
  '/discrepancy-taxonomy',
  '/docs',
  '/api',
];

/**
 * Legal placeholder surfaces — kept noindex until operator/legal provides
 * approved copy. They must still resolve, must carry an explicit
 * legal_review_required status string, and must not invent legal promises.
 */
export const D5_LEGAL_PLACEHOLDER_ROUTES = ['/privacy', '/terms', '/gdpr'];

/**
 * Reserved infrastructure/doc URLs linked from the site but not yet
 * published as indexable proof surfaces (noindex placeholders).
 */
export const D5_RESERVED_DOC_PLACEHOLDER_ROUTES = ['/security'];

/**
 * Union of every route the D5 directive requires to exist.
 */
export const D5_REQUIRED_ROUTES = [
  ...D5_LEGAL_PLACEHOLDER_ROUTES,
  ...D5_INDEXABLE_PROOF_ROUTES,
  ...D5_RESERVED_DOC_PLACEHOLDER_ROUTES,
];

/**
 * Required visible concept markers per route. Each value is an array of
 * substring patterns (case-insensitive). Every entry must appear in the
 * route's static HTML; otherwise the page is judged to fail its
 * advertised purpose.
 *
 * The markers are deliberately short and conservative so they remain
 * stable across copy revisions.
 */
export const D5_REQUIRED_CONCEPTS = {
  '/trust-envelope': [
    'deterministic values',
    'provenance chain',
    'semantic truth hash',
    'artifact hash',
    'confidence status',
    'benchmark metadata',
    'policy authority',
    'fallback reason',
    'external verification metadata',
    'action authority',
    'audit trail',
    'limitations',
  ],
  '/methodology': [
    'deterministic',
    'verified evidence',
    'attribution model',
    'discrepancy',
    'limitations',
  ],
  '/ai-boundary': [
    'llm',
    'does not calculate',
    'deterministic',
    'explanations',
    'limitations',
  ],
  '/revenue-verification': [
    'commerce evidence',
    'payment evidence',
    'reconciliation',
    'discrepancy',
    'limitations',
  ],
  '/attribution-methodology': [
    'attribution model',
    'bounded',
    'assumptions',
    'limitations',
  ],
  '/discrepancy-taxonomy': [
    'timing mismatch',
    'currency',
    'refund',
    'attribution-window',
    'duplicate',
    'missing commerce event',
    'unmatched platform claim',
    'delayed arrival',
    'limitations',
  ],
  '/docs': [
    'documentation',
    'concepts',
    'availability',
  ],
  '/api': [
    'api',
    'availability',
    'concepts',
  ],
};

/**
 * Phrases that, if present in any source file under `src/`, indicate an
 * invented or operator-unapproved compliance/security claim. Real D5
 * passing state allows these phrases only when they appear inside an
 * approved-evidence block that is logged in the claim-proof registry.
 *
 * The default policy is: ALL of these phrases must NOT appear in source
 * unless they appear inside a quoted-status taxonomy ("we do not claim
 * SOC 2") or inside the registry as a `status: not_claimed` row.
 */
export const D5_BANNED_UNAPPROVED_COMPLIANCE_PHRASES = [
  // Certifications - banned unless registry marks status approved with evidence
  'SOC 2 certified',
  'SOC2 certified',
  'ISO 27001 certified',
  'ISO certified',
  'HIPAA compliant',
  'PCI DSS compliant',
  'PCI compliant',
  'GDPR compliant',
  'CCPA compliant',
  'FedRAMP authorized',
  // Encryption-as-fact - banned without scope qualifier
  'fully encrypted',
  'end-to-end encrypted',
  // Absolute privacy guarantees - banned (overclaim risk)
  'we never store any PII',
  'we collect no PII',
  'we collect zero data',
  'cannot be hacked',
];

/**
 * Indexable proof pages must carry a recognized review-status token so a
 * skeptical reviewer can confirm the page is operator-acknowledged.
 */
export const D5_REVIEW_STATUS_TOKENS = [
  'operator_approved',
  'technical_disclosure_only',
  'legal_review_required',
  'blocked_missing_content',
];

/**
 * High-stakes claim trigger terms. If any of these phrases appears in
 * source under `src/app` or `src/components`, the claim must be mapped
 * to a proof route in the claim-proof registry.
 *
 * Triggers are case-insensitive substring matches.
 */
export const D5_HIGH_STAKES_CLAIM_TRIGGERS = [
  'verified',
  'deterministic',
  'financial truth',
  'TrustEnvelope',
  'source of truth',
  'audit',
  'no PII',
  'commerce evidence',
  'policy authority',
  'AI Agents',
];

/**
 * Required claim-proof registry fields per claim entry.
 */
export const D5_CLAIM_REGISTRY_REQUIRED_FIELDS = [
  'claim_id',
  'claim_text',
  'source_route',
  'claim_category',
  'risk_level',
  'proof_route',
  'proof_anchor',
  'proof_type',
  'owner',
  'legal_review_required',
  'status',
  'last_reviewed',
];

export const D5_CLAIM_CATEGORIES = [
  'revenue_verification',
  'deterministic_truth',
  'privacy_no_pii',
  'ai_boundary',
  'auditability',
  'trust_envelope',
  'attribution_methodology',
  'discrepancy_handling',
  'benchmark_confidence',
  'security',
];

/**
 * Compute the on-disk static export path for a logical route, mirroring
 * `src/lib/crawlUrls.ts → routeToOutputPath`. Returns an absolute path
 * under `out/`.
 *
 * @param {string} marketingRoot
 * @param {string} logicalPath - e.g. "/methodology"
 * @returns {string}
 */
export function logicalPathToOutHtml(marketingRoot, logicalPath) {
  const p = logicalPath === '/' ? '/' : logicalPath.startsWith('/') ? logicalPath : `/${logicalPath}`;
  const rel = p === '/' ? 'index.html' : `${p.replace(/^\//, '')}.html`;
  return path.join(marketingRoot, 'out', rel.split('/').join(path.sep));
}

/**
 * Walk every page.tsx file under `src/app/` and return the logical route
 * paths that have a real `page.tsx` (i.e. routes Next will emit). Used
 * by Gate D5.1 to confirm required routes exist as source.
 *
 * @param {string} marketingRoot
 * @returns {Set<string>}
 */
export function discoverAppRouterRoutes(marketingRoot) {
  const appDir = path.join(marketingRoot, 'src', 'app');
  /** @type {Set<string>} */
  const routes = new Set();
  /** @param {string} d */
  function walk(d) {
    if (!fs.existsSync(d)) return;
    for (const ent of fs.readdirSync(d, { withFileTypes: true })) {
      if (ent.isDirectory()) {
        if (ent.name.startsWith('_') || ent.name === 'node_modules') continue;
        walk(path.join(d, ent.name));
      } else if (/^page\.(tsx|ts|jsx|js)$/.test(ent.name)) {
        const rel = path.relative(appDir, d).split(path.sep).join('/');
        const logical = rel === '' ? '/' : `/${rel}`;
        routes.add(logical);
      }
    }
  }
  walk(appDir);
  return routes;
}

/**
 * Read the rendered static HTML for a logical route. Returns null if the
 * file is missing.
 *
 * @param {string} marketingRoot
 * @param {string} logicalPath
 * @returns {string|null}
 */
export function readBuiltHtml(marketingRoot, logicalPath) {
  const abs = logicalPathToOutHtml(marketingRoot, logicalPath);
  if (!fs.existsSync(abs)) return null;
  return fs.readFileSync(abs, 'utf8');
}

/**
 * Strip HTML tags from a string. Used only for concept-substring matching;
 * we want concepts to be visible to humans, not hidden in attribute
 * values.
 *
 * @param {string} html
 * @returns {string}
 */
export function visibleTextOnly(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/g, ' ')
    .replace(/\s+/g, ' ');
}

/**
 * Confirm a built proof page meets the D5 baseline:
 *   - H1 present (or h1 aria-label)
 *   - Canonical present and pointing to the expected logical path
 *   - Title present
 *   - Meta description present
 *   - Visible review-status token from D5_REVIEW_STATUS_TOKENS
 *
 * @param {string} marketingRoot
 * @param {string} logicalPath
 * @param {string} html
 * @returns {string[]} errors
 */
export function validateD5ProofPageBaseline(marketingRoot, logicalPath, html) {
  /** @type {string[]} */
  const errors = [];
  const auth = readCrawlUrlAuthority(marketingRoot);
  const origin = auth.SITE_ORIGIN;
  const expectedCanonical =
    logicalPath === '/' ? `${origin}/` : `${origin}${logicalPath.startsWith('/') ? logicalPath : `/${logicalPath}`}`;

  const title = extractTitle(html);
  if (!title) errors.push(`${logicalPath}: missing <title>`);

  const desc = extractMetaDescription(html);
  if (!desc) errors.push(`${logicalPath}: missing meta description`);

  const canonical = extractCanonicalHref(html);
  if (!canonical) {
    errors.push(`${logicalPath}: missing <link rel="canonical">`);
  } else if (canonical !== expectedCanonical) {
    errors.push(
      `${logicalPath}: canonical mismatch — expected ${expectedCanonical}, got ${canonical}`,
    );
  }

  const h1 = extractPrimaryH1Text(html);
  if (!h1) errors.push(`${logicalPath}: indexable proof page must expose a primary <h1>`);

  const visible = visibleTextOnly(html);

  const hasReviewStatus = D5_REVIEW_STATUS_TOKENS.some((tok) =>
    new RegExp(`\\b${tok.replace(/_/g, '[_ ]')}\\b`, 'i').test(visible),
  );
  if (!hasReviewStatus) {
    errors.push(
      `${logicalPath}: proof page must expose a review-status token (${D5_REVIEW_STATUS_TOKENS.join('|')})`,
    );
  }

  if (htmlHasNoindexRobots(html)) {
    errors.push(
      `${logicalPath}: indexable proof page must NOT carry meta robots noindex (must be a public proof surface)`,
    );
  }

  if (/Loading\.\.\./.test(html) || /animate-pulse/.test(html)) {
    errors.push(
      `${logicalPath}: proof page must not emit a Loading shell — static HTML must contain the proof content`,
    );
  }

  return errors;
}

/**
 * Confirm a proof page contains every required concept marker for that
 * route.
 *
 * @param {string} logicalPath
 * @param {string} html
 * @returns {string[]} errors
 */
export function validateD5ProofPageConcepts(logicalPath, html) {
  /** @type {string[]} */
  const errors = [];
  const concepts = D5_REQUIRED_CONCEPTS[logicalPath];
  if (!concepts) return errors;
  const visible = visibleTextOnly(html).toLowerCase();
  for (const c of concepts) {
    if (!visible.includes(c.toLowerCase())) {
      errors.push(`${logicalPath}: missing required concept marker "${c}"`);
    }
  }
  return errors;
}

/**
 * Legal placeholder routes must:
 *   - exist
 *   - carry an explicit legal_review_required status string in static HTML
 *   - not invent compliance/security promises
 *   - be noindex (until legal copy is approved)
 *   - emit a canonical pointing to themselves
 *
 * @param {string} marketingRoot
 * @param {string} logicalPath
 * @param {string} html
 * @returns {string[]}
 */
export function validateD5LegalPlaceholder(marketingRoot, logicalPath, html) {
  /** @type {string[]} */
  const errors = [];
  const auth = readCrawlUrlAuthority(marketingRoot);
  const origin = auth.SITE_ORIGIN;
  const expectedCanonical = `${origin}${logicalPath}`;

  if (!extractTitle(html)) errors.push(`${logicalPath}: legal placeholder missing <title>`);
  if (!extractMetaDescription(html)) errors.push(`${logicalPath}: legal placeholder missing meta description`);

  const canonical = extractCanonicalHref(html);
  if (canonical && canonical !== expectedCanonical) {
    errors.push(`${logicalPath}: canonical must be ${expectedCanonical}, got ${canonical}`);
  }

  if (!extractPrimaryH1Text(html)) {
    errors.push(`${logicalPath}: legal placeholder must expose a primary <h1>`);
  }

  if (!htmlHasNoindexRobots(html)) {
    errors.push(
      `${logicalPath}: legal placeholder must remain noindex until operator/legal supplies approved copy`,
    );
  }

  const visible = visibleTextOnly(html);
  if (!/legal[_\s-]review[_\s-]required|blocked[_\s-]missing[_\s-]content/i.test(visible)) {
    errors.push(
      `${logicalPath}: legal placeholder must declare explicit status (legal_review_required | blocked_missing_content)`,
    );
  }

  const invented = scanInventedComplianceClaims(html);
  if (invented.length > 0) {
    for (const phrase of invented) {
      errors.push(
        `${logicalPath}: legal placeholder must not invent compliance/security claim "${phrase}"`,
      );
    }
  }

  return errors;
}

/**
 * Scan visible HTML for banned compliance/security phrases. Returns the
 * matched phrases. Used by both indexable and placeholder routes.
 *
 * @param {string} html
 * @returns {string[]}
 */
export function scanInventedComplianceClaims(html) {
  const visible = visibleTextOnly(html);
  /** @type {string[]} */
  const hits = [];
  for (const phrase of D5_BANNED_UNAPPROVED_COMPLIANCE_PHRASES) {
    const re = new RegExp(phrase.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i');
    if (re.test(visible)) hits.push(phrase);
  }
  return hits;
}

/**
 * Footer/legal/navigation link policy: no legal/security/docs/API
 * label may point to `/resources`, and the required legal labels must
 * resolve to the canonical D5 routes.
 *
 * Returns errors when any banned target is found or when a required
 * label is missing.
 *
 * @param {string} marketingRoot
 * @returns {string[]}
 */
export function validateFooterLegalLinkPolicy(marketingRoot) {
  /** @type {string[]} */
  const errors = [];
  const footerPath = path.join(marketingRoot, 'src', 'components', 'layout', 'Footer.tsx');
  if (!fs.existsSync(footerPath)) {
    errors.push('Footer.tsx not found at expected path src/components/layout/Footer.tsx');
    return errors;
  }
  const src = fs.readFileSync(footerPath, 'utf8');

  /**
   * @type {Array<{ label: string; expectedHref: string }>}
   */
  const requiredLinks = [
    { label: 'Privacy Policy', expectedHref: '/privacy' },
    { label: 'Terms of Service', expectedHref: '/terms' },
    { label: 'GDPR', expectedHref: '/gdpr' },
    { label: 'Security', expectedHref: '/security' },
    { label: 'Documentation', expectedHref: '/docs' },
    { label: 'API Reference', expectedHref: '/api' },
    { label: 'Methodology', expectedHref: '/methodology' },
    { label: 'TrustEnvelope', expectedHref: '/trust-envelope' },
  ];

  for (const link of requiredLinks) {
    const labelEsc = link.label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const labelPresent = new RegExp(`label:\\s*["']${labelEsc}["']`, 'i').test(src);
    if (!labelPresent) {
      errors.push(`Footer.tsx: missing required link label "${link.label}"`);
      continue;
    }
    const expectedEsc = link.expectedHref.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const wiredCorrectly = new RegExp(
      `label:\\s*["']${labelEsc}["']\\s*,\\s*href:\\s*["']${expectedEsc}["']`,
      'i',
    ).test(src);
    if (!wiredCorrectly) {
      errors.push(
        `Footer.tsx: link "${link.label}" must point to "${link.expectedHref}" (D5 legal/proof route)`,
      );
    }
  }

  /** Forbid legal/security/docs/API labels pointing to /resources */
  const bannedTargetsForLegalLabels = [
    'Privacy Policy',
    'Terms of Service',
    'GDPR',
    'Security',
    'Documentation',
    'API Reference',
    'Methodology',
    'TrustEnvelope',
  ];
  for (const label of bannedTargetsForLegalLabels) {
    const labelEsc = label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    if (new RegExp(`label:\\s*["']${labelEsc}["'][^}]*href:\\s*["']/resources(?:["'/])`, 'i').test(src)) {
      errors.push(`Footer.tsx: legal/proof label "${label}" must not point to /resources`);
    }
  }

  return errors;
}

/**
 * Validate the book-demo form does not link to an undefined /privacy
 * route. /privacy must exist as static HTML at out/privacy.html for D5.
 *
 * @param {string} marketingRoot
 * @returns {string[]}
 */
export function validateBookDemoPrivacyLink(marketingRoot) {
  /** @type {string[]} */
  const errors = [];
  const bdPath = path.join(marketingRoot, 'src', 'app', 'book-demo', 'page.tsx');
  if (!fs.existsSync(bdPath)) return errors;
  const src = fs.readFileSync(bdPath, 'utf8');
  if (!/href=["']\/privacy["']/i.test(src)) {
    errors.push('book-demo/page.tsx: must link to /privacy (currently missing the Privacy Policy link)');
    return errors;
  }
  const privacyHtml = readBuiltHtml(marketingRoot, '/privacy');
  if (privacyHtml === null) {
    errors.push('book-demo links to /privacy, but out/privacy.html does not exist (404 for crawlers)');
  }
  return errors;
}

/**
 * Load the machine-readable claim-proof registry. Throws if missing
 * or shape-invalid (so the harness fails loudly).
 *
 * @param {string} marketingRoot
 * @returns {{ registry: any, claims: any[] }}
 */
export function loadClaimProofRegistry(marketingRoot) {
  const p = path.join(marketingRoot, 'discoverability.claim-proof-registry.json');
  if (!fs.existsSync(p)) {
    throw new Error(`Missing discoverability.claim-proof-registry.json at ${p}`);
  }
  const j = JSON.parse(fs.readFileSync(p, 'utf8'));
  if (!Array.isArray(j.claims)) {
    throw new Error('claim-proof registry must contain top-level "claims" array');
  }
  return { registry: j, claims: j.claims };
}

/**
 * Validate each claim entry includes the required fields, points at a
 * known D5 proof route, and uses a recognized category.
 *
 * @param {string} marketingRoot
 * @returns {string[]} errors
 */
export function validateClaimProofRegistryShape(marketingRoot) {
  /** @type {string[]} */
  const errors = [];
  let claims;
  try {
    ({ claims } = loadClaimProofRegistry(marketingRoot));
  } catch (e) {
    errors.push(e.message);
    return errors;
  }
  const seenIds = new Set();
  for (let i = 0; i < claims.length; i++) {
    const c = claims[i];
    if (!c || typeof c !== 'object') {
      errors.push(`claim[${i}]: not an object`);
      continue;
    }
    for (const f of D5_CLAIM_REGISTRY_REQUIRED_FIELDS) {
      if (!(f in c)) {
        errors.push(`claim[${i}] (${c.claim_id || 'unknown'}): missing required field "${f}"`);
      }
    }
    if (c.claim_id) {
      if (seenIds.has(c.claim_id)) {
        errors.push(`claim[${i}]: duplicate claim_id "${c.claim_id}"`);
      }
      seenIds.add(c.claim_id);
    }
    if (c.claim_category && !D5_CLAIM_CATEGORIES.includes(c.claim_category)) {
      errors.push(
        `claim[${i}] (${c.claim_id}): unknown claim_category "${c.claim_category}" (allowed: ${D5_CLAIM_CATEGORIES.join(', ')})`,
      );
    }
    if (c.proof_route && !D5_REQUIRED_ROUTES.includes(c.proof_route)) {
      errors.push(
        `claim[${i}] (${c.claim_id}): proof_route "${c.proof_route}" is not a D5 required route`,
      );
    }
  }
  return errors;
}

/**
 * Validate each registered claim has its referenced anchor present in the
 * built proof HTML. Anchors look like `#section-id` and must appear as
 * `id="section-id"` somewhere in the static HTML.
 *
 * @param {string} marketingRoot
 * @returns {string[]}
 */
export function validateClaimProofAnchorsExist(marketingRoot) {
  /** @type {string[]} */
  const errors = [];
  let claims;
  try {
    ({ claims } = loadClaimProofRegistry(marketingRoot));
  } catch (e) {
    errors.push(e.message);
    return errors;
  }
  /** @type {Record<string, string | null>} */
  const htmlCache = {};
  for (const c of claims) {
    const route = c.proof_route;
    if (!route) continue;
    if (!(route in htmlCache)) {
      htmlCache[route] = readBuiltHtml(marketingRoot, route);
    }
    const html = htmlCache[route];
    if (html === null) {
      errors.push(`claim ${c.claim_id}: proof_route ${route} has no built HTML (out${route}.html missing)`);
      continue;
    }
    const anchor = String(c.proof_anchor || '').replace(/^#/, '');
    if (!anchor) {
      errors.push(`claim ${c.claim_id}: proof_anchor is required`);
      continue;
    }
    const idRe = new RegExp(`\\bid=["']${anchor.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}["']`);
    if (!idRe.test(html)) {
      errors.push(
        `claim ${c.claim_id}: proof_anchor #${anchor} not found in built HTML for ${route}`,
      );
    }
  }
  return errors;
}

/**
 * Scan source for high-stakes claim trigger phrases. Returns a map of
 * trigger → list of matched file paths (so the operator can quickly see
 * where each unregistered claim lives).
 *
 * Used by Gate D5.2 to confirm every trigger appearance is covered by a
 * claim-proof registry entry (matched by source_route).
 *
 * @param {string} marketingRoot
 * @returns {Record<string, string[]>}
 */
export function scanHighStakesClaimSources(marketingRoot) {
  /** @type {Record<string, string[]>} */
  const result = {};
  const roots = [
    path.join(marketingRoot, 'src', 'app'),
    path.join(marketingRoot, 'src', 'components'),
  ];
  /** @type {string[]} */
  const files = [];
  /** @param {string} d */
  function walk(d) {
    if (!fs.existsSync(d)) return;
    for (const ent of fs.readdirSync(d, { withFileTypes: true })) {
      const p = path.join(d, ent.name);
      if (ent.isDirectory()) {
        if (ent.name.startsWith('_') || ent.name === 'node_modules') continue;
        walk(p);
      } else if (/\.(tsx|ts|jsx|js|md|mdx)$/.test(ent.name)) {
        files.push(p);
      }
    }
  }
  for (const r of roots) walk(r);
  for (const trigger of D5_HIGH_STAKES_CLAIM_TRIGGERS) {
    /** @type {string[]} */
    const hits = [];
    const re = new RegExp(trigger.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i');
    for (const f of files) {
      const txt = fs.readFileSync(f, 'utf8');
      if (re.test(txt)) hits.push(path.relative(marketingRoot, f).replace(/\\/g, '/'));
    }
    result[trigger] = hits;
  }
  return result;
}
