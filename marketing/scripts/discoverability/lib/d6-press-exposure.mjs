/**
 * D6-b — /press designed-absence, IP exposure, media overclaim, and contact validation.
 */

import fs from 'node:fs';
import path from 'node:path';

export const D6B_PRESS_ROUTE = '/press';
export const D6B_PUBLIC_CONTACTS_FILENAME = 'discoverability.public-contacts.json';
export const D6B_PRESS_REGISTRY_FILENAME = 'discoverability.press-registry.json';

/** Phrases allowed only inside explicit non-disclosure boundary sentences. */
export const D6B_PRESS_NEGATIVE_BOUNDARY_CONTEXT =
  /not disclosed publicly|are not disclosed publicly|does not publicly disclose|will not publicly disclose|not disclose publicly/i;

export const D6B_PRESS_FORBIDDEN_PLACEHOLDER_REGEXES = [
  { id: 'technical_disclosure_only_token', pattern: /\btechnical_disclosure_only\b/i },
  { id: 'legal_review_required_token', pattern: /\blegal_review_required\b/i },
  { id: 'owner_registry_slug', pattern: /Owner_Skeldir_Product_Engineering/i },
  { id: 'coming_soon', pattern: /\bcoming soon\b/i },
  { id: 'press_kit_coming_soon', pattern: /\bpress kit coming soon\b/i },
  { id: 'media_kit_coming_soon', pattern: /\bmedia kit coming soon\b/i },
  { id: 'under_construction', pattern: /\bunder construction\b/i },
  { id: 'placeholder', pattern: /\bplaceholder\b/i },
  { id: 'draft', pattern: /\bdraft\b/i },
  { id: 'tbd', pattern: /\bTBD\b/ },
];

export const D6B_PRESS_FORBIDDEN_IMPLEMENTATION_REGEXES = [
  { id: 'trust_envelope_contracts', pattern: /\bTrustEnvelope contracts\b/i },
  { id: 'enumerated_contract_fields', pattern: /\benumerated contract fields\b/i },
  { id: 'field_schema', pattern: /\bfield schema\b/i },
  { id: 'payload_schema', pattern: /\bpayload schema\b/i },
  { id: 'machine_callable_contract', pattern: /\bmachine-callable contract\b/i },
  { id: 'backend_roadmap', pattern: /\bbackend roadmap\b/i },
  { id: 'unannounced_integration_details', pattern: /\bunannounced integration details\b/i },
  { id: 'implementation_modules_positive', pattern: /\bimplementation modules\b/i, negativeOk: true },
  { id: 'phase_identifiers_positive', pattern: /\bphase identifiers\b/i, negativeOk: true },
  { id: 'schema_details_positive', pattern: /\bschema details\b/i, negativeOk: true },
  { id: 'pipeline_specifics_positive', pattern: /\bpipeline specifics\b/i, negativeOk: true },
  { id: 'internal_architecture_positive', pattern: /\binternal architecture\b/i, negativeOk: true },
];

export const D6B_PRESS_FORBIDDEN_MEDIA_CLAIM_REGEXES = [
  { id: 'market_leader', pattern: /\bmarket leader\b/i },
  { id: 'category_creator', pattern: /\bcategory creator\b/i },
  { id: 'fastest_growing', pattern: /\bfastest-growing\b/i },
  { id: 'trusted_by_leading', pattern: /\btrusted by leading brands\b/i },
  { id: 'revenue_growth', pattern: /\brevenue growth\b/i },
  { id: 'funding_amount', pattern: /\bfunding amount\b/i },
  { id: 'customer_count', pattern: /\bcustomer count\b/i },
  { id: 'partnership_announcement', pattern: /\bpartnership announcement\b/i },
  { id: 'award_winning', pattern: /\baward-winning\b/i },
  { id: 'as_seen_in', pattern: /\bas seen in\b/i },
];

export const D6B_PRESS_REQUIRED_MARKERS = [
  'Press',
  'Bottom Line Up Front',
  'Key facts',
  'Technical disclosures',
  'Inquiry routing',
  'Scope of public information',
  'Contact',
  'Last updated',
];

export const D6B_PRESS_BOUNDARY_MARKERS = [
  'published methodology',
  'unpublished capabilities',
  'unannounced integrations',
  'revenue projections',
  'roadmap',
];

export const D6B_PRESS_REQUIRED_LINKS = [
  '/methodology',
  '/revenue-verification',
  '/attribution-methodology',
  '/discrepancy-taxonomy',
  '/trust-envelope',
  '/ai-boundary',
  '/security',
  '/status',
];

const EMAIL_RE = /[a-z0-9._%+-]+@skeldir\.com/gi;

/**
 * @param {string} marketingRoot
 * @returns {{ contacts: object[] }}
 */
export function loadPublicContactsRegistry(marketingRoot) {
  const p = path.join(marketingRoot, D6B_PUBLIC_CONTACTS_FILENAME);
  if (!fs.existsSync(p)) {
    throw new Error(`Missing ${D6B_PUBLIC_CONTACTS_FILENAME} at ${p}`);
  }
  const j = JSON.parse(fs.readFileSync(p, 'utf8'));
  if (!Array.isArray(j.contacts)) {
    throw new Error(`${D6B_PUBLIC_CONTACTS_FILENAME} must contain contacts array`);
  }
  return j;
}

/**
 * @param {string} marketingRoot
 * @returns {object}
 */
export function loadPressRegistry(marketingRoot) {
  const p = path.join(marketingRoot, D6B_PRESS_REGISTRY_FILENAME);
  if (!fs.existsSync(p)) {
    throw new Error(`Missing ${D6B_PRESS_REGISTRY_FILENAME} at ${p}`);
  }
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}

/**
 * @param {string} html
 * @param {RegExp} pattern
 * @returns {boolean}
 */
function matchInNegativeBoundaryOnly(html, pattern) {
  const re = new RegExp(pattern.source, pattern.flags.includes('g') ? pattern.flags : `${pattern.flags}g`);
  let m;
  while ((m = re.exec(html)) !== null) {
    const start = Math.max(0, m.index - 120);
    const end = Math.min(html.length, m.index + m[0].length + 120);
    const ctx = html.slice(start, end);
    if (!D6B_PRESS_NEGATIVE_BOUNDARY_CONTEXT.test(ctx)) {
      return false;
    }
  }
  return true;
}

/**
 * @param {string} html
 * @param {{ contacts: object[] }} contactsRegistry
 * @param {object} pressRegistry
 * @param {{ sitemapPaths?: Set<string> }} [opts]
 * @returns {string[]}
 */
export function validateD6PressExposure(html, contactsRegistry, pressRegistry, opts = {}) {
  const errors = [];
  if (!html || html.length < 1000) {
    errors.push(`${D6B_PRESS_ROUTE}: HTML unexpectedly short`);
    return errors;
  }

  const lower = html.toLowerCase();
  const approvedRenderEmails = new Set(
    (contactsRegistry.contacts || [])
      .filter((c) => c.publicly_rendered)
      .map((c) => String(c.email || '').toLowerCase()),
  );

  for (const { id, pattern } of D6B_PRESS_FORBIDDEN_PLACEHOLDER_REGEXES) {
    if (pattern.test(html)) {
      errors.push(`${D6B_PRESS_ROUTE}: forbidden D6-b pattern "${id}"`);
    }
  }

  for (const { id, pattern, negativeOk } of D6B_PRESS_FORBIDDEN_IMPLEMENTATION_REGEXES) {
    if (!pattern.test(html)) continue;
    if (negativeOk && matchInNegativeBoundaryOnly(html, pattern)) continue;
    errors.push(`${D6B_PRESS_ROUTE}: forbidden D6-b pattern "${id}"`);
  }

  const approvedMedia = pressRegistry.approved_media_claims || [];
  for (const { id, pattern } of D6B_PRESS_FORBIDDEN_MEDIA_CLAIM_REGEXES) {
    if (pattern.test(html)) {
      const ok = approvedMedia.some((claim) => pattern.test(claim));
      if (!ok) errors.push(`${D6B_PRESS_ROUTE}: forbidden media claim "${id}"`);
    }
  }

  for (const marker of D6B_PRESS_REQUIRED_MARKERS) {
    if (!html.includes(marker) && !lower.includes(marker.toLowerCase())) {
      errors.push(`${D6B_PRESS_ROUTE}: missing required marker "${marker}"`);
    }
  }

  for (const marker of D6B_PRESS_BOUNDARY_MARKERS) {
    if (!lower.includes(marker.toLowerCase())) {
      errors.push(`${D6B_PRESS_ROUTE}: missing boundary marker "${marker}"`);
    }
  }

  for (const href of D6B_PRESS_REQUIRED_LINKS) {
    if (!html.includes(`href="${href}"`) && !html.includes(`href='${href}'`)) {
      errors.push(`${D6B_PRESS_ROUTE}: missing proof link ${href}`);
    }
  }

  const foundEmails = new Set();
  let em;
  const emailScan = new RegExp(EMAIL_RE.source, EMAIL_RE.flags);
  while ((em = emailScan.exec(html)) !== null) {
    foundEmails.add(em[0].toLowerCase());
  }
  for (const email of foundEmails) {
    if (!approvedRenderEmails.has(email)) {
      errors.push(`${D6B_PRESS_ROUTE}: unapproved public email "${email}"`);
    }
  }
  if (!foundEmails.has('press@skeldir.com')) {
    errors.push(`${D6B_PRESS_ROUTE}: missing approved press contact press@skeldir.com`);
  }

  if (pressRegistry.indexability && htmlHasNoindexRobots(html)) {
    errors.push(`${D6B_PRESS_ROUTE}: registry requires indexable page but HTML is noindex`);
  }

  if (pressRegistry.sitemap_required && opts.sitemapPaths && !opts.sitemapPaths.has(D6B_PRESS_ROUTE)) {
    errors.push(`${D6B_PRESS_ROUTE}: registry requires sitemap inclusion`);
  }

  if (!/<h1[\s>]/i.test(html)) {
    errors.push(`${D6B_PRESS_ROUTE}: missing <h1>`);
  }

  if (/Loading\.\.\.|animate-pulse|Redirecting/i.test(html)) {
    errors.push(`${D6B_PRESS_ROUTE}: loading shell or redirect detected`);
  }

  return errors;
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
