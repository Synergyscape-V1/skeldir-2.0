/**
 * D6-b — /careers designed-absence, IP exposure, hiring overclaim, contact, and schema checks.
 */

import fs from 'node:fs';
import path from 'node:path';

export const D6B_CAREERS_ROUTE = '/careers';
export const D6B_CAREERS_REGISTRY_FILENAME = 'discoverability.careers-registry.json';
export const D6B_PUBLIC_CONTACTS_FILENAME = 'discoverability.public-contacts.json';

const EMAIL_RE = /[a-z0-9._%+-]+@skeldir\.com/gi;

export const D6B_CAREERS_FORBIDDEN_PLACEHOLDER_REGEXES = [
  { id: 'technical_disclosure_only_token', pattern: /\btechnical_disclosure_only\b/i },
  { id: 'legal_review_required_token', pattern: /\blegal_review_required\b/i },
  { id: 'owner_registry_slug', pattern: /Owner_Skeldir_Product_Engineering/i },
  { id: 'coming_soon', pattern: /\bcoming soon\b/i },
  { id: 'roles_coming_soon', pattern: /\broles coming soon\b/i },
  { id: 'under_construction', pattern: /\bunder construction\b/i },
  { id: 'placeholder', pattern: /\bplaceholder\b/i },
  { id: 'draft', pattern: /\bdraft\b/i },
  { id: 'tbd', pattern: /\bTBD\b/ },
];

export const D6B_CAREERS_FORBIDDEN_IMPLEMENTATION_REGEXES = [
  { id: 'row_level_security', pattern: /\brow-level security\b/i },
  { id: 'rls', pattern: /\bRLS\b/ },
  { id: 'guc', pattern: /\bGUC\b/ },
  { id: 'cryptographic_signing', pattern: /\bcryptographic signing\b/i },
  { id: 'canonical_serialization', pattern: /\bcanonical serialization\b/i },
  { id: 'tenant_isolation_implementation', pattern: /\btenant isolation implementation\b/i },
  { id: 'database_isolation', pattern: /\bdatabase isolation\b/i },
  { id: 'ci_as_adjudication', pattern: /\bCI as adjudication\b/i },
  { id: 'trust_envelope_internals', pattern: /\bTrustEnvelope internals\b/i },
  { id: 'reconciliation_engine_internals', pattern: /\breconciliation engine internals\b/i },
  { id: 'hashing_strategy', pattern: /\bhashing strategy\b/i },
];

export const D6B_CAREERS_FORBIDDEN_ACTIVE_HIRING_REGEXES = [
  { id: 'we_are_hiring', pattern: /\bwe are hiring\b/i },
  { id: 'current_open_roles', pattern: /\bcurrent open roles\b/i },
  { id: 'view_open_roles', pattern: /\bview (?:our )?open roles\b/i },
  { id: 'apply_now', pattern: /\bapply now\b/i },
  { id: 'join_the_team', pattern: /\bjoin the team\b/i },
  { id: 'submit_resume', pattern: /\bsubmit your resume\b/i },
  { id: 'send_portfolio', pattern: /\bsend your portfolio\b/i },
  { id: 'job_posting_text', pattern: /\bjob posting\b/i },
];

export const D6B_CAREERS_FORBIDDEN_BENEFIT_REGEXES = [
  { id: 'remote_first', pattern: /\bremote-first\b/i },
  { id: 'fully_remote', pattern: /\bfully remote\b/i },
  { id: 'competitive_salary', pattern: /\bcompetitive salary\b/i },
  { id: 'equity', pattern: /\bequity\b/i },
  { id: 'health_benefits', pattern: /\bhealth benefits\b/i },
  { id: '401k', pattern: /\b401k\b/i },
  { id: 'unlimited_pto', pattern: /\bunlimited PTO\b/i },
  { id: 'visa_sponsorship', pattern: /\bvisa sponsorship\b/i },
  { id: 'rapidly_growing', pattern: /\brapidly growing\b/i },
  { id: 'backed_by', pattern: /\bbacked by\b/i },
  { id: 'funded_by', pattern: /\bfunded by\b/i },
  { id: 'world_class_team', pattern: /\bworld-class team\b/i },
];

export const D6B_CAREERS_FORBIDDEN_JOB_SCHEMA_REGEXES = [
  { id: 'job_posting_schema', pattern: /\bJobPosting\b/ },
  { id: 'employment_type', pattern: /\bemploymentType\b/ },
  { id: 'base_salary', pattern: /\bbaseSalary\b/ },
  { id: 'valid_through', pattern: /\bvalidThrough\b/ },
  { id: 'applicant_location', pattern: /\bapplicantLocationRequirements\b/ },
];

export const D6B_CAREERS_REQUIRED_MARKERS = [
  'Careers',
  'Bottom Line Up Front',
  'Key facts',
  'What We Value',
  'How We Hire',
  'How to Express Interest',
  'Scope and Trust Boundary',
  'Contact',
  'Last updated',
];

export const D6B_CAREERS_DESIGNED_ABSENCE_MARKERS = [
  'not a job board',
  'no public roles',
  'not an exhaustive list',
];

/**
 * @param {string} marketingRoot
 * @returns {object}
 */
export function loadCareersRegistry(marketingRoot) {
  const p = path.join(marketingRoot, D6B_CAREERS_REGISTRY_FILENAME);
  if (!fs.existsSync(p)) {
    throw new Error(`Missing ${D6B_CAREERS_REGISTRY_FILENAME} at ${p}`);
  }
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}

/**
 * @param {string} marketingRoot
 * @returns {{ contacts: object[] }}
 */
export function loadPublicContactsForCareers(marketingRoot) {
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
 * @param {object} careersRegistry
 * @param {{ contacts: object[] }} contactsRegistry
 * @param {{ sitemapPaths?: Set<string> }} [opts]
 * @returns {string[]}
 */
export function validateD6CareersExposure(html, careersRegistry, contactsRegistry, opts = {}) {
  const errors = [];
  if (!html || html.length < 900) {
    errors.push(`${D6B_CAREERS_ROUTE}: HTML unexpectedly short`);
    return errors;
  }

  const lower = html.toLowerCase();
  const approvedRenderEmails = new Set(
    (contactsRegistry.contacts || [])
      .filter((c) => c.publicly_rendered)
      .map((c) => String(c.email || '').toLowerCase()),
  );
  const approvedBenefits = careersRegistry.approved_benefit_claims || [];
  const activeRoles = Number(careersRegistry.active_roles_count || 0);
  const jobPostingAllowed = careersRegistry.job_posting_allowed === true && activeRoles > 0;

  for (const { id, pattern } of D6B_CAREERS_FORBIDDEN_PLACEHOLDER_REGEXES) {
    if (pattern.test(html)) {
      errors.push(`${D6B_CAREERS_ROUTE}: forbidden D6-b pattern "${id}"`);
    }
  }

  for (const { id, pattern } of D6B_CAREERS_FORBIDDEN_IMPLEMENTATION_REGEXES) {
    if (pattern.test(html)) {
      errors.push(`${D6B_CAREERS_ROUTE}: forbidden D6-b pattern "${id}"`);
    }
  }

  if (activeRoles === 0) {
    for (const { id, pattern } of D6B_CAREERS_FORBIDDEN_ACTIVE_HIRING_REGEXES) {
      if (pattern.test(html)) {
        errors.push(`${D6B_CAREERS_ROUTE}: forbidden active-hiring pattern "${id}" (active_roles_count=0)`);
      }
    }
  }

  for (const { id, pattern } of D6B_CAREERS_FORBIDDEN_BENEFIT_REGEXES) {
    if (pattern.test(html)) {
      const ok = approvedBenefits.some((claim) => pattern.test(claim));
      if (!ok) errors.push(`${D6B_CAREERS_ROUTE}: forbidden benefit claim "${id}"`);
    }
  }

  if (!jobPostingAllowed) {
    for (const { id, pattern } of D6B_CAREERS_FORBIDDEN_JOB_SCHEMA_REGEXES) {
      if (pattern.test(html)) {
        errors.push(`${D6B_CAREERS_ROUTE}: forbidden job schema pattern "${id}"`);
      }
    }
  }

  for (const marker of D6B_CAREERS_REQUIRED_MARKERS) {
    if (!html.includes(marker) && !lower.includes(marker.toLowerCase())) {
      errors.push(`${D6B_CAREERS_ROUTE}: missing required marker "${marker}"`);
    }
  }

  for (const marker of D6B_CAREERS_DESIGNED_ABSENCE_MARKERS) {
    if (!lower.includes(marker.toLowerCase())) {
      errors.push(`${D6B_CAREERS_ROUTE}: missing designed-absence marker "${marker}"`);
    }
  }

  const talentEmail = String(careersRegistry.talent_contact_channel || '').toLowerCase();
  if (!careersRegistry.contact_approved) {
    errors.push(`${D6B_CAREERS_ROUTE}: careers registry contact_approved is false`);
  }
  if (!talentEmail) {
    errors.push(`${D6B_CAREERS_ROUTE}: missing talent_contact_channel in careers registry`);
  } else if (!approvedRenderEmails.has(talentEmail)) {
    errors.push(`${D6B_CAREERS_ROUTE}: talent contact "${talentEmail}" not approved in public contacts registry`);
  } else if (!html.toLowerCase().includes(talentEmail)) {
    errors.push(`${D6B_CAREERS_ROUTE}: missing talent contact channel in HTML`);
  }

  const foundEmails = new Set();
  let em;
  const emailScan = new RegExp(EMAIL_RE.source, EMAIL_RE.flags);
  while ((em = emailScan.exec(html)) !== null) {
    foundEmails.add(em[0].toLowerCase());
  }
  for (const email of foundEmails) {
    if (!approvedRenderEmails.has(email)) {
      errors.push(`${D6B_CAREERS_ROUTE}: unapproved public email "${email}"`);
    }
  }

  if (careersRegistry.indexability && htmlHasNoindexRobots(html)) {
    errors.push(`${D6B_CAREERS_ROUTE}: registry requires indexable page but HTML is noindex`);
  }

  if (careersRegistry.sitemap_required && opts.sitemapPaths && !opts.sitemapPaths.has(D6B_CAREERS_ROUTE)) {
    errors.push(`${D6B_CAREERS_ROUTE}: registry requires sitemap inclusion`);
  }

  if (!/<h1[\s>]/i.test(html)) {
    errors.push(`${D6B_CAREERS_ROUTE}: missing <h1>`);
  }

  if (/Loading\.\.\.|animate-pulse|Redirecting/i.test(html)) {
    errors.push(`${D6B_CAREERS_ROUTE}: loading shell or redirect detected`);
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
