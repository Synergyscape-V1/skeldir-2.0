/**
 * D6-b — /about entity positioning, IP exposure, overclaim, and D4 semantics alignment.
 */

import fs from 'node:fs';
import path from 'node:path';
import {
  loadEntitySemanticsRegistry,
  validateD6EntitySemanticsDrift,
} from './d6-entity-semantics.mjs';

export const D6B_ABOUT_ROUTE = '/about';
export const D6B_ABOUT_REGISTRY_FILENAME = 'discoverability.about-surface-registry.json';

export const D6B_ABOUT_FORBIDDEN_PLACEHOLDER_REGEXES = [
  { id: 'technical_disclosure_only_token', pattern: /\btechnical_disclosure_only\b/i },
  { id: 'legal_review_required_token', pattern: /\blegal_review_required\b/i },
  { id: 'owner_registry_slug', pattern: /Owner_Skeldir_Product_Engineering/i },
  { id: 'coming_soon', pattern: /\bcoming soon\b/i },
  { id: 'under_construction', pattern: /\bunder construction\b/i },
  { id: 'placeholder', pattern: /\bplaceholder\b/i },
  { id: 'draft', pattern: /\bdraft\b/i },
  { id: 'tbd', pattern: /\bTBD\b/ },
];

export const D6B_ABOUT_FORBIDDEN_IMPLEMENTATION_REGEXES = [
  { id: 'integer_cents_reconciliation', pattern: /\binteger-cents reconciliation\b/i },
  { id: 'integer_minor_units', pattern: /\binteger minor units\b/i },
  { id: 'commerce_orders', pattern: /\bcommerce orders\b/i },
  { id: 'payment_settlements', pattern: /\bpayment settlements\b/i },
  { id: 'normalizes_them', pattern: /\bnormalizes them\b/i },
  { id: 'deterministic_computation_engine', pattern: /\bdeterministic computation engine\b/i },
  { id: 'query_record_output', pattern: /\bquery, record, and deterministic output\b/i },
  { id: 'cross_tenant_structurally_prevented', pattern: /\bcross-tenant data access is structurally prevented\b/i },
  { id: 'cross_tenant_structurally_prevented_alt', pattern: /\bcross-tenant access is structurally prevented\b/i },
  { id: 'pii_is_stripped', pattern: /\bPII is stripped\b/i },
  { id: 'durable_storage', pattern: /\bdurable storage\b/i },
  { id: 'machine_readable_trust_record', pattern: /\bmachine-readable trust record\b/i },
  { id: 'governing_policy_context', pattern: /\bgoverning policy context\b/i },
  { id: 'full_provenance', pattern: /\bfull provenance\b/i },
  { id: 'full_audit_trail', pattern: /\bfull audit trail\b/i },
  { id: 'configure_reconciliation_policy', pattern: /\bconfigure reconciliation policy\b/i },
  { id: 'database_word', pattern: /\bdatabase\b/i },
  { id: 'worker_word', pattern: /\bworker\b/i },
  { id: 'pipeline_word', pattern: /\bpipeline\b/i },
  { id: 'schema_word', pattern: /\bschema\b/i },
  { id: 'hash_word', pattern: /\bhash\b/i },
  { id: 'signing_word', pattern: /\bsigning\b/i },
];

export const D6B_ABOUT_FORBIDDEN_ABSOLUTE_REGEXES = [
  { id: 'every_output_carries', pattern: /\bevery output carries\b/i },
  { id: 'every_query', pattern: /\bevery query\b/i },
  { id: 'every_record', pattern: /\bevery record\b/i },
  { id: 'no_pii', pattern: /\bno PII\b/i },
  { id: 'zero_pii', pattern: /\bzero PII\b/i },
  { id: 'does_not_survive_durable_storage', pattern: /\bdoes not survive into durable storage\b/i },
  { id: 'does_not_survive_durable_storage_alt', pattern: /\bdoes not survive durable storage\b/i },
  { id: 'guaranteed', pattern: /\bguaranteed\b/i },
  { id: 'sovereign_truth', pattern: /\bsovereign truth\b/i },
];

/** Primary positioning failures (positive claims without negation). */
export const D6B_ABOUT_DISALLOWED_PRIMARY_REGEXES = [
  {
    id: 'primary_ai_attribution_assistant',
    pattern: /Skeldir is an? AI attribution assistant/i,
  },
  {
    id: 'primary_analytics_dashboard',
    pattern: /Skeldir is an? analytics dashboard/i,
  },
  {
    id: 'primary_ad_optimization',
    pattern: /Skeldir is an? ad optimization/i,
  },
  {
    id: 'primary_financial_product',
    pattern: /Skeldir is a financial product/i,
  },
  {
    id: 'primary_bayesian_truth',
    pattern: /Bayesian truth engine/i,
  },
];

export const D6B_ABOUT_REQUIRED_MARKERS = [
  'About Skeldir',
  'Bottom Line Up Front',
  'Key facts',
  'What Skeldir Does',
  'Principles That Govern Skeldir',
  'Who Skeldir Serves',
  'How Skeldir Differs From Analytics and Attribution Platforms',
  'How Organizations Engage With Skeldir',
  'Last updated',
];

export const D6B_ABOUT_REQUIRED_LINKS = [
  '/methodology',
  '/revenue-verification',
  '/attribution-methodology',
  '/discrepancy-taxonomy',
  '/trust-envelope',
  '/ai-boundary',
  '/security',
  '/privacy',
  '/api',
  '/docs',
];

/**
 * @param {string} marketingRoot
 * @returns {object}
 */
export function loadAboutSurfaceRegistry(marketingRoot) {
  const p = path.join(marketingRoot, D6B_ABOUT_REGISTRY_FILENAME);
  if (!fs.existsSync(p)) {
    throw new Error(`Missing ${D6B_ABOUT_REGISTRY_FILENAME} at ${p}`);
  }
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}

/**
 * @param {string} html
 * @returns {string}
 */
function htmlVisibleForExposureScan(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ');
}

/**
 * @param {string} html
 * @returns {boolean}
 */
function htmlHasNoindexRobots(html) {
  const re = /<meta[^>]*name=["']robots["'][^>]*content=["']([^"']+)["']/gi;
  let m;
  while ((m = re.exec(html)) !== null) {
    if (m[1].toLowerCase().includes('noindex')) return true;
  }
  return false;
}

/**
 * @param {string} html
 * @param {object} aboutRegistry
 * @param {{ sitemapPaths?: Set<string>; marketingRoot?: string }} [opts]
 * @returns {string[]}
 */
export function validateD6AboutExposure(html, aboutRegistry, opts = {}) {
  const errors = [];
  if (!html || html.length < 900) {
    errors.push(`${D6B_ABOUT_ROUTE}: HTML unexpectedly short`);
    return errors;
  }

  const lower = html.toLowerCase();
  const marketingRoot = opts.marketingRoot;
  const visibleHtml = htmlVisibleForExposureScan(html);

  for (const { id, pattern } of D6B_ABOUT_FORBIDDEN_PLACEHOLDER_REGEXES) {
    if (pattern.test(visibleHtml)) {
      errors.push(`${D6B_ABOUT_ROUTE}: forbidden D6-b pattern "${id}"`);
    }
  }

  for (const { id, pattern } of [
    ...D6B_ABOUT_FORBIDDEN_IMPLEMENTATION_REGEXES,
    ...D6B_ABOUT_FORBIDDEN_ABSOLUTE_REGEXES,
    ...D6B_ABOUT_DISALLOWED_PRIMARY_REGEXES,
  ]) {
    if (pattern.test(visibleHtml)) {
      errors.push(`${D6B_ABOUT_ROUTE}: forbidden D6-b pattern "${id}"`);
    }
  }

  for (const marker of D6B_ABOUT_REQUIRED_MARKERS) {
    if (!html.includes(marker) && !lower.includes(marker.toLowerCase())) {
      errors.push(`${D6B_ABOUT_ROUTE}: missing required marker "${marker}"`);
    }
  }

  const canon = String(aboutRegistry.canonical_entity_definition || '');
  if (canon) {
    const canonCore = canon.slice(0, Math.min(80, canon.length));
    if (!lower.includes(canonCore.toLowerCase().slice(0, 40))) {
      if (
        !lower.includes('financial-trust infrastructure') ||
        !lower.includes('deterministic revenue verification')
      ) {
        errors.push(
          `${D6B_ABOUT_ROUTE}: missing canonical entity definition markers (financial-trust + deterministic revenue verification)`,
        );
      }
    }
  }

  for (const phrase of aboutRegistry.required_boundary_phrases || []) {
    if (!lower.includes(String(phrase).toLowerCase())) {
      errors.push(`${D6B_ABOUT_ROUTE}: missing registry boundary phrase "${phrase}"`);
    }
  }

  for (const term of aboutRegistry.approved_positioning_terms || []) {
    if (!lower.includes(String(term).toLowerCase())) {
      errors.push(`${D6B_ABOUT_ROUTE}: missing approved positioning term "${term}"`);
    }
  }

  for (const href of D6B_ABOUT_REQUIRED_LINKS) {
    if (!html.includes(`href="${href}"`) && !html.includes(`href='${href}'`)) {
      errors.push(`${D6B_ABOUT_ROUTE}: missing proof link ${href}`);
    }
  }

  if (aboutRegistry.indexability && htmlHasNoindexRobots(html)) {
    errors.push(`${D6B_ABOUT_ROUTE}: registry requires indexable page but HTML is noindex`);
  }

  if (aboutRegistry.sitemap_required && opts.sitemapPaths && !opts.sitemapPaths.has(D6B_ABOUT_ROUTE)) {
    errors.push(`${D6B_ABOUT_ROUTE}: registry requires sitemap inclusion`);
  }

  if (!/<h1[\s>]/i.test(html)) {
    errors.push(`${D6B_ABOUT_ROUTE}: missing <h1>`);
  }

  if (/Loading\.\.\.|animate-pulse|Redirecting/i.test(html)) {
    errors.push(`${D6B_ABOUT_ROUTE}: loading shell or redirect detected`);
  }

  if (marketingRoot) {
    try {
      const entityReg = loadEntitySemanticsRegistry(marketingRoot);
      const drift = validateD6EntitySemanticsDrift(D6B_ABOUT_ROUTE, html, entityReg);
      errors.push(...drift.errors);
    } catch (e) {
      errors.push(`${D6B_ABOUT_ROUTE}: entity semantics registry: ${e.message}`);
    }
  }

  return errors;
}
