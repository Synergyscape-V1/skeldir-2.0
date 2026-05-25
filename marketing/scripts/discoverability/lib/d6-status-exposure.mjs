/**
 * D6-b — /status designed-absence, overclaim, and registry alignment checks.
 */

import fs from 'node:fs';
import path from 'node:path';

export const D6B_STATUS_ROUTE = '/status';
export const D6B_STATUS_REGISTRY_FILENAME = 'discoverability.status-registry.json';

export const D6B_STATUS_FORBIDDEN_PLACEHOLDER_REGEXES = [
  { id: 'technical_disclosure_only_token', pattern: /\btechnical_disclosure_only\b/i },
  { id: 'legal_review_required_token', pattern: /\blegal_review_required\b/i },
  { id: 'owner_registry_slug', pattern: /Owner_Skeldir_Product_Engineering/i },
  { id: 'coming_soon', pattern: /\bcoming soon\b/i },
  { id: 'under_construction', pattern: /\bunder construction\b/i },
  { id: 'placeholder', pattern: /\bplaceholder\b/i },
  { id: 'draft', pattern: /\bdraft\b/i },
  { id: 'tbd', pattern: /\bTBD\b/ },
];

export const D6B_STATUS_FORBIDDEN_OVERCLAIM_REGEXES = [
  { id: 'fully_operational', pattern: /\bfully operational\b/i },
  { id: 'all_systems_operational', pattern: /\ball systems operational\b/i },
  { id: 'all_core_systems', pattern: /\ball core systems\b/i },
  { id: 'processing_normally', pattern: /\bprocessing normally\b/i },
  { id: 'sla', pattern: /\bSLA\b/ },
  { id: 'uptime_guarantee', pattern: /\buptime guarantee\b/i },
  { id: 'live_real_time_status', pattern: /\blive real-time status\b/i },
  { id: 'positive_automated_feed', pattern: /(?<!not an )automated real-time feed/i },
  { id: 'no_outages_ever', pattern: /\bno outages ever\b/i },
  { id: 'uptime_999', pattern: /99\.9\s*%/ },
];

export const D6B_STATUS_REQUIRED_MARKERS = [
  'Status',
  'Key facts',
  'Current status',
  'Active incidents',
  'Scheduled maintenance',
  'Communication',
  'Scope',
  'Report an issue',
  'Last updated',
];

export const D6B_STATUS_MANUAL_BOUNDARY_MARKERS = [
  'manually verified',
  'not an automated real-time',
];

export const D6B_STATUS_REQUIRED_LINKS = [
  '/security',
  '/privacy',
  '/methodology',
  '/trust-envelope',
  '/docs',
];

/**
 * @param {string} marketingRoot
 * @returns {object}
 */
export function loadStatusRegistry(marketingRoot) {
  const p = path.join(marketingRoot, D6B_STATUS_REGISTRY_FILENAME);
  if (!fs.existsSync(p)) {
    throw new Error(`Missing ${D6B_STATUS_REGISTRY_FILENAME} at ${p}`);
  }
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}

/**
 * @param {string} html
 * @param {object} registry
 * @param {{ sitemapPaths?: Set<string> }} [opts]
 * @returns {string[]}
 */
export function validateD6StatusExposure(html, registry, opts = {}) {
  const errors = [];
  if (!html || html.length < 800) {
    errors.push(`${D6B_STATUS_ROUTE}: HTML unexpectedly short`);
    return errors;
  }

  const lower = html.toLowerCase();

  for (const { id, pattern } of [
    ...D6B_STATUS_FORBIDDEN_PLACEHOLDER_REGEXES,
    ...D6B_STATUS_FORBIDDEN_OVERCLAIM_REGEXES,
  ]) {
    if (pattern.test(html)) {
      const approved = (registry.approved_operational_claims || []).some((claim) =>
        pattern.test(claim),
      );
      if (!approved) {
        errors.push(`${D6B_STATUS_ROUTE}: forbidden D6-b pattern "${id}"`);
      }
    }
  }

  for (const marker of D6B_STATUS_REQUIRED_MARKERS) {
    if (!html.includes(marker) && !lower.includes(marker.toLowerCase())) {
      errors.push(`${D6B_STATUS_ROUTE}: missing required marker "${marker}"`);
    }
  }

  const manualOk = D6B_STATUS_MANUAL_BOUNDARY_MARKERS.some(
    (m) => html.includes(m) || lower.includes(m.toLowerCase()),
  );
  if (!manualOk) {
    errors.push(`${D6B_STATUS_ROUTE}: missing manual status boundary`);
  }

  for (const href of D6B_STATUS_REQUIRED_LINKS) {
    if (!html.includes(`href="${href}"`) && !html.includes(`href='${href}'`)) {
      errors.push(`${D6B_STATUS_ROUTE}: missing link ${href}`);
    }
  }

  const incidents = registry.active_incidents || [];
  if (incidents.length === 0) {
    if (!/no active incidents/i.test(html)) {
      errors.push(`${D6B_STATUS_ROUTE}: registry has no incidents but page missing "no active incidents"`);
    }
  }

  const maintenance = registry.scheduled_maintenance || [];
  if (maintenance.length === 0) {
    if (!/no scheduled maintenance/i.test(html)) {
      errors.push(
        `${D6B_STATUS_ROUTE}: registry has no maintenance but page missing "no scheduled maintenance"`,
      );
    }
  }

  const contact = registry.operator_contact_channel;
  if (contact && !html.includes(contact)) {
    errors.push(`${D6B_STATUS_ROUTE}: missing operator contact channel "${contact}"`);
  }

  if (registry.indexability && htmlHasNoindexRobots(html)) {
    errors.push(`${D6B_STATUS_ROUTE}: registry requires indexable page but HTML is noindex`);
  }

  if (registry.sitemap_required && opts.sitemapPaths) {
    if (!opts.sitemapPaths.has(D6B_STATUS_ROUTE)) {
      errors.push(`${D6B_STATUS_ROUTE}: registry requires sitemap inclusion`);
    }
  }

  if (!/<h1[\s>]/i.test(html)) {
    errors.push(`${D6B_STATUS_ROUTE}: missing <h1>`);
  }

  if (/Loading\.\.\.|animate-pulse|Redirecting/i.test(html)) {
    errors.push(`${D6B_STATUS_ROUTE}: loading shell or redirect detected`);
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
