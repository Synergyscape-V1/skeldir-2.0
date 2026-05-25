/**
 * D6-b — /api access boundary, contract leakage, and contact validation.
 */

import fs from 'node:fs';
import path from 'node:path';

export const D6B_API_ROUTE = '/api';
export const D6B_API_SURFACE_REGISTRY_FILENAME = 'discoverability.api-surface-registry.json';
export const D6B_PUBLIC_CONTACTS_FILENAME = 'discoverability.public-contacts.json';

const EMAIL_RE = /[a-z0-9._%+-]+@skeldir\.com/gi;

export const D6B_API_FORBIDDEN_PLACEHOLDER_REGEXES = [
  { id: 'technical_disclosure_only_token', pattern: /\btechnical_disclosure_only\b/i },
  { id: 'legal_review_required_token', pattern: /\blegal_review_required\b/i },
  { id: 'owner_registry_slug', pattern: /Owner_Skeldir_Product_Engineering/i },
  { id: 'coming_soon', pattern: /\bcoming soon\b/i },
  { id: 'api_coming_soon', pattern: /\bAPI coming soon\b/i },
  { id: 'under_construction', pattern: /\bunder construction\b/i },
  { id: 'placeholder', pattern: /\bplaceholder\b/i },
  { id: 'draft', pattern: /\bdraft\b/i },
  { id: 'tbd', pattern: /\bTBD\b/ },
];

export const D6B_API_FORBIDDEN_CONTRACT_REGEXES = [
  { id: 'endpoint_url', pattern: /\bendpoint URL\b/i },
  { id: 'endpoint_address', pattern: /\bendpoint address\b/i },
  { id: 'get_slash', pattern: /\bGET\s+\//i },
  { id: 'post_slash', pattern: /\bPOST\s+\//i },
  { id: 'openapi', pattern: /\bOpenAPI\b/i },
  { id: 'swagger', pattern: /\bSwagger\b/i },
  { id: 'authentication_scheme', pattern: /\bauthentication scheme\b/i },
  { id: 'bearer_token', pattern: /\bBearer token\b/i },
  { id: 'api_key', pattern: /\bAPI key\b/i },
  { id: 'oauth', pattern: /\bOAuth\b/i },
  { id: 'versioning_policy', pattern: /\bversioning policy\b/i },
  { id: 'payload_schema', pattern: /\bpayload schema\b/i },
  { id: 'field_schema', pattern: /\bfield schema\b/i },
  { id: 'response_schema', pattern: /\bresponse schema\b/i },
  { id: 'webhook_schema', pattern: /\bwebhook schema\b/i },
  { id: 'sdk', pattern: /\bSDK\b/ },
  { id: 'curl_example', pattern: /\bcurl example\b/i },
  { id: 'json_response', pattern: /\bJSON response\b/i },
  { id: 'machine_callable_contract', pattern: /\bmachine-callable contract\b/i },
  { id: 'trust_envelope_contract', pattern: /\bTrustEnvelope contract\b/i },
];

export const D6B_API_FORBIDDEN_SHAPE_REGEXES = [
  { id: 'semantic_truth_hash', pattern: /\bsemantic truth hash\b/i },
  { id: 'artifact_hash', pattern: /\bartifact hash\b/i },
  { id: 'evidence_reference_set', pattern: /\bevidence reference set\b/i },
  { id: 'record_integrity_metadata', pattern: /\brecord integrity metadata\b/i },
  { id: 'policy_object', pattern: /\bpolicy object\b/i },
  { id: 'enumerated_verification_status', pattern: /\benumerated verification status\b/i },
  { id: 'integer_minor_units', pattern: /\binteger minor units\b/i },
  { id: 'action_authority', pattern: /\baction authority\b/i },
  { id: 'operational_decision_boundary_encoded', pattern: /\boperational decision boundary encoded\b/i },
  { id: 'allowed_operational_scope_documented', pattern: /\ballowed operational scope documented\b/i },
];

export const D6B_API_REQUIRED_MARKERS = [
  'API',
  'Bottom Line Up Front',
  'Key facts',
  'What API access represents',
  'What context accompanies programmatic output',
  'How agents consume Skeldir output responsibly',
  'How access is governed',
  'Current operational boundaries',
  'Last updated',
];

export const D6B_API_REQUIRED_LINKS = [
  '/trust-envelope',
  '/methodology',
  '/revenue-verification',
  '/ai-boundary',
  '/security',
  '/docs',
  '/privacy',
];

/**
 * @param {string} marketingRoot
 * @returns {object}
 */
export function loadApiSurfaceRegistry(marketingRoot) {
  const p = path.join(marketingRoot, D6B_API_SURFACE_REGISTRY_FILENAME);
  if (!fs.existsSync(p)) {
    throw new Error(`Missing ${D6B_API_SURFACE_REGISTRY_FILENAME} at ${p}`);
  }
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}

/**
 * @param {string} marketingRoot
 * @returns {{ contacts: object[] }}
 */
export function loadPublicContactsForApi(marketingRoot) {
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
 * @param {object} apiRegistry
 * @param {{ contacts: object[] }} contactsRegistry
 * @param {{ sitemapPaths?: Set<string> }} [opts]
 * @returns {string[]}
 */
export function validateD6ApiExposure(html, apiRegistry, contactsRegistry, opts = {}) {
  const errors = [];
  if (!html || html.length < 900) {
    errors.push(`${D6B_API_ROUTE}: HTML unexpectedly short`);
    return errors;
  }

  const lower = html.toLowerCase();
  const publicRef = apiRegistry.public_api_reference_available === true;
  const approvedRenderEmails = new Set(
    (contactsRegistry.contacts || [])
      .filter((c) => c.publicly_rendered)
      .map((c) => String(c.email || '').toLowerCase()),
  );

  for (const { id, pattern } of D6B_API_FORBIDDEN_PLACEHOLDER_REGEXES) {
    if (pattern.test(html)) {
      errors.push(`${D6B_API_ROUTE}: forbidden D6-b pattern "${id}"`);
    }
  }

  if (!publicRef) {
    for (const { id, pattern } of [
      ...D6B_API_FORBIDDEN_CONTRACT_REGEXES,
      ...D6B_API_FORBIDDEN_SHAPE_REGEXES,
    ]) {
      if (pattern.test(html)) {
        errors.push(`${D6B_API_ROUTE}: forbidden D6-b pattern "${id}"`);
      }
    }
  }

  if (apiRegistry.public_endpoint_details_rendered && !publicRef) {
    errors.push(
      `${D6B_API_ROUTE}: public_endpoint_details_rendered requires public_api_reference_available`,
    );
  }

  for (const marker of D6B_API_REQUIRED_MARKERS) {
    if (!html.includes(marker) && !lower.includes(marker.toLowerCase())) {
      errors.push(`${D6B_API_ROUTE}: missing required marker "${marker}"`);
    }
  }

  for (const phrase of apiRegistry.required_boundary_phrases || []) {
    if (!lower.includes(String(phrase).toLowerCase())) {
      errors.push(`${D6B_API_ROUTE}: missing registry boundary phrase "${phrase}"`);
    }
  }

  for (const href of D6B_API_REQUIRED_LINKS) {
    if (!html.includes(`href="${href}"`) && !html.includes(`href='${href}'`)) {
      errors.push(`${D6B_API_ROUTE}: missing proof link ${href}`);
    }
  }

  const contactEmail = String(apiRegistry.contact_channel || '').toLowerCase();
  if (!apiRegistry.contact_approved) {
    errors.push(`${D6B_API_ROUTE}: api registry contact_approved is false`);
  }
  if (contactEmail && !approvedRenderEmails.has(contactEmail)) {
    errors.push(`${D6B_API_ROUTE}: contact "${contactEmail}" not approved in public contacts registry`);
  } else if (contactEmail && !html.toLowerCase().includes(contactEmail)) {
    errors.push(`${D6B_API_ROUTE}: missing integration contact channel in HTML`);
  }

  const foundEmails = new Set();
  let em;
  const emailScan = new RegExp(EMAIL_RE.source, EMAIL_RE.flags);
  while ((em = emailScan.exec(html)) !== null) {
    foundEmails.add(em[0].toLowerCase());
  }
  for (const email of foundEmails) {
    if (!approvedRenderEmails.has(email)) {
      errors.push(`${D6B_API_ROUTE}: unapproved public email "${email}"`);
    }
  }

  if (apiRegistry.indexability && htmlHasNoindexRobots(html)) {
    errors.push(`${D6B_API_ROUTE}: registry requires indexable page but HTML is noindex`);
  }

  if (apiRegistry.sitemap_required && opts.sitemapPaths && !opts.sitemapPaths.has(D6B_API_ROUTE)) {
    errors.push(`${D6B_API_ROUTE}: registry requires sitemap inclusion`);
  }

  if (!/<h1[\s>]/i.test(html)) {
    errors.push(`${D6B_API_ROUTE}: missing <h1>`);
  }

  if (/Loading\.\.\.|animate-pulse|Redirecting/i.test(html)) {
    errors.push(`${D6B_API_ROUTE}: loading shell or redirect detected`);
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
