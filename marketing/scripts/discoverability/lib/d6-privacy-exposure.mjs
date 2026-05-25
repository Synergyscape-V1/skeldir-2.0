/**
 * D6-b — /privacy posture, implementation leakage, overclaim, and contact validation.
 */

import fs from 'node:fs';
import path from 'node:path';

export const D6B_PRIVACY_ROUTE = '/privacy';
export const D6B_PRIVACY_REGISTRY_FILENAME = 'discoverability.privacy-surface-registry.json';
export const D6B_PUBLIC_CONTACTS_FILENAME = 'discoverability.public-contacts.json';

const EMAIL_RE = /[a-z0-9._%+-]+@skeldir\.com/gi;

export const D6B_PRIVACY_FORBIDDEN_PLACEHOLDER_REGEXES = [
  { id: 'legal_review_required_token', pattern: /\blegal_review_required\b/i },
  { id: 'technical_disclosure_only_token', pattern: /\btechnical_disclosure_only\b/i },
  { id: 'undergoing_review', pattern: /\bundergoing review\b/i },
  { id: 'will_be_published_at_url', pattern: /\bwill be published at this URL\b/i },
  { id: 'upon_completion', pattern: /\bupon completion\b/i },
  { id: 'owner_registry_slug', pattern: /Owner_Skeldir_Product_Engineering/i },
  { id: 'coming_soon', pattern: /\bcoming soon\b/i },
  { id: 'under_construction', pattern: /\bunder construction\b/i },
  { id: 'placeholder', pattern: /\bplaceholder\b/i },
  { id: 'draft', pattern: /\bdraft\b/i },
  { id: 'tbd', pattern: /\bTBD\b/ },
];

export const D6B_PRIVACY_FORBIDDEN_IMPLEMENTATION_REGEXES = [
  { id: 'hmac', pattern: /\bHMAC\b/ },
  { id: 'rsa', pattern: /\bRSA\b/ },
  { id: 'webhook_receiver', pattern: /\bwebhook receiver\b/i },
  { id: 'authenticated_webhook', pattern: /\bauthenticated webhook\b/i },
  { id: 'signature_verification', pattern: /\bsignature verification\b/i },
  { id: 'tenant_context', pattern: /\btenant context\b/i },
  { id: 'row_level_security', pattern: /\brow-level security\b/i },
  { id: 'rls', pattern: /\bRLS\b/ },
  { id: 'database_layer', pattern: /\bdatabase layer\b/i },
  { id: 'query_scoping', pattern: /\bquery scoping\b/i },
  { id: 'worker_operation', pattern: /\bworker operation\b/i },
  { id: 'cache_entry', pattern: /\bcache entry\b/i },
  { id: 'trust_envelope_scoped', pattern: /\bTrustEnvelope scoped\b/i },
  { id: 'k_anonymity', pattern: /\bk-anonymity\b/i },
  { id: 'dominance_suppression', pattern: /\bdominance suppression\b/i },
  { id: 'benchmark_seeding', pattern: /\bbenchmark seeding\b/i },
  { id: 'historical_corpus', pattern: /\bhistorical corpus\b/i },
  { id: 'pii_stripping_implementation', pattern: /\bPII stripping implementation\b/i },
];

export const D6B_PRIVACY_FORBIDDEN_OVERCLAIM_REGEXES = [
  { id: 'gdpr_compliant', pattern: /\bGDPR compliant\b/i },
  { id: 'ccpa_compliant', pattern: /\bCCPA compliant\b/i },
  { id: 'data_subject_rights_procedure', pattern: /\bdata subject rights procedure\b/i },
  { id: 'retention_schedule', pattern: /\bretention schedule\b/i },
  { id: 'subprocessor_list', pattern: /\bsubprocessor list\b/i },
  { id: 'transfer_mechanism', pattern: /\btransfer mechanism\b/i },
  { id: 'dpa_available', pattern: /\bDPA available\b/i },
  { id: 'zero_pii', pattern: /\bzero PII\b/i },
  { id: 'no_pii', pattern: /\bno PII\b/i },
  { id: 'no_durable_pii', pattern: /\bno durable PII\b/i },
  { id: 'never_stores_personal_data', pattern: /\bnever stores personal data\b/i },
  { id: 'fully_anonymized', pattern: /\bfully anonymized\b/i },
  { id: 'anonymous_data', pattern: /\banonymous data\b/i },
];

export const D6B_PRIVACY_REQUIRED_MARKERS = [
  'Privacy',
  'Bottom Line Up Front',
  'Key facts',
  'Privacy posture',
  'Data Skeldir processes',
  'Data minimization',
  'Tenant-scoped data handling',
  'Legal and operator documentation boundary',
  'Contact',
  'Last updated',
];

export const D6B_PRIVACY_REQUIRED_LINKS = [
  '/security',
  '/methodology',
  '/revenue-verification',
  '/trust-envelope',
  '/ai-boundary',
  '/gdpr',
];

/**
 * @param {string} marketingRoot
 * @returns {object}
 */
export function loadPrivacySurfaceRegistry(marketingRoot) {
  const p = path.join(marketingRoot, D6B_PRIVACY_REGISTRY_FILENAME);
  if (!fs.existsSync(p)) {
    throw new Error(`Missing ${D6B_PRIVACY_REGISTRY_FILENAME} at ${p}`);
  }
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}

/**
 * @param {string} marketingRoot
 * @returns {{ contacts: object[] }}
 */
export function loadPublicContactsForPrivacy(marketingRoot) {
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
 * @param {object} privacyRegistry
 * @param {{ contacts: object[] }} contactsRegistry
 * @param {{ sitemapPaths?: Set<string> }} [opts]
 * @returns {string[]}
 */
export function validateD6PrivacyExposure(html, privacyRegistry, contactsRegistry, opts = {}) {
  const errors = [];
  if (!html || html.length < 900) {
    errors.push(`${D6B_PRIVACY_ROUTE}: HTML unexpectedly short`);
    return errors;
  }

  const lower = html.toLowerCase();
  const approvedClaims = new Set(
    (privacyRegistry.allowed_claims || []).map((c) => String(c).toLowerCase()),
  );
  const approvedRenderEmails = new Set(
    (contactsRegistry.contacts || [])
      .filter((c) => c.publicly_rendered)
      .map((c) => String(c.email || '').toLowerCase()),
  );

  for (const { id, pattern } of D6B_PRIVACY_FORBIDDEN_PLACEHOLDER_REGEXES) {
    if (pattern.test(html)) {
      errors.push(`${D6B_PRIVACY_ROUTE}: forbidden D6-b pattern "${id}"`);
    }
  }

  for (const { id, pattern } of D6B_PRIVACY_FORBIDDEN_IMPLEMENTATION_REGEXES) {
    if (pattern.test(html)) {
      errors.push(`${D6B_PRIVACY_ROUTE}: forbidden D6-b pattern "${id}"`);
    }
  }

  const legalApproved = privacyRegistry.legal_review_status === 'approved';
  if (!legalApproved) {
    for (const { id, pattern } of D6B_PRIVACY_FORBIDDEN_OVERCLAIM_REGEXES) {
      if (pattern.test(html)) {
        errors.push(`${D6B_PRIVACY_ROUTE}: forbidden D6-b pattern "${id}"`);
      }
    }
  } else {
    for (const claim of privacyRegistry.disallowed_claims || []) {
      const re = new RegExp(claim.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i');
      if (re.test(html) && !approvedClaims.has(String(claim).toLowerCase())) {
        errors.push(`${D6B_PRIVACY_ROUTE}: disallowed claim "${claim}" without registry approval`);
      }
    }
  }

  if (privacyRegistry.public_page_type === 'legal_privacy_policy' && !legalApproved) {
    errors.push(
      `${D6B_PRIVACY_ROUTE}: legal_privacy_policy requires legal_review_status approved`,
    );
  }

  if (privacyRegistry.legal_review_status === 'pending') {
    if (!/not a complete legal privacy policy/i.test(html)) {
      errors.push(
        `${D6B_PRIVACY_ROUTE}: pending legal review must state page is not a complete legal privacy policy`,
      );
    }
  }

  for (const marker of D6B_PRIVACY_REQUIRED_MARKERS) {
    if (!html.includes(marker) && !lower.includes(marker.toLowerCase())) {
      errors.push(`${D6B_PRIVACY_ROUTE}: missing required marker "${marker}"`);
    }
  }

  for (const phrase of privacyRegistry.required_boundary_phrases || []) {
    if (!lower.includes(String(phrase).toLowerCase())) {
      errors.push(`${D6B_PRIVACY_ROUTE}: missing registry boundary phrase "${phrase}"`);
    }
  }

  for (const href of D6B_PRIVACY_REQUIRED_LINKS) {
    if (!html.includes(`href="${href}"`) && !html.includes(`href='${href}'`)) {
      errors.push(`${D6B_PRIVACY_ROUTE}: missing proof link ${href}`);
    }
  }

  if (!privacyRegistry.contact_approved) {
    errors.push(`${D6B_PRIVACY_ROUTE}: privacy registry contact_approved is false`);
  }

  for (const email of privacyRegistry.contact_channels || []) {
    const norm = String(email).toLowerCase();
    if (!approvedRenderEmails.has(norm)) {
      errors.push(`${D6B_PRIVACY_ROUTE}: contact "${norm}" not approved in public contacts registry`);
    } else if (!html.toLowerCase().includes(norm)) {
      errors.push(`${D6B_PRIVACY_ROUTE}: missing approved contact "${norm}" in HTML`);
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
      errors.push(`${D6B_PRIVACY_ROUTE}: unapproved public email "${email}"`);
    }
  }

  if (privacyRegistry.indexability === false && !htmlHasNoindexRobots(html)) {
    errors.push(`${D6B_PRIVACY_ROUTE}: registry requires noindex but HTML is indexable`);
  }

  if (
    privacyRegistry.sitemap_required === false &&
    opts.sitemapPaths &&
    opts.sitemapPaths.has(D6B_PRIVACY_ROUTE)
  ) {
    errors.push(`${D6B_PRIVACY_ROUTE}: registry excludes sitemap but route is in manifest`);
  }

  if (privacyRegistry.sitemap_required && opts.sitemapPaths && !opts.sitemapPaths.has(D6B_PRIVACY_ROUTE)) {
    errors.push(`${D6B_PRIVACY_ROUTE}: registry requires sitemap inclusion`);
  }

  if (!/<h1[\s>]/i.test(html)) {
    errors.push(`${D6B_PRIVACY_ROUTE}: missing <h1>`);
  }

  if (/Loading\.\.\.|animate-pulse|Redirecting/i.test(html)) {
    errors.push(`${D6B_PRIVACY_ROUTE}: loading shell or redirect detected`);
  }

  return errors;
}
