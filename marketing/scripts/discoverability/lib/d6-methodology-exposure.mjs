/**
 * D6-b — /methodology IP exposure and placeholder-theater checks.
 */

export const D6B_METHODOLOGY_ROUTE = '/methodology';

/** Fatal if present in built /methodology HTML (internal badges or implementation leakage). */
export const D6B_METHODOLOGY_FORBIDDEN_REGEXES = [
  { id: 'technical_disclosure_only_token', pattern: /\btechnical_disclosure_only\b/i },
  { id: 'legal_review_required_token', pattern: /\blegal_review_required\b/i },
  { id: 'owner_registry_slug', pattern: /Owner_Skeldir_Product_Engineering/i },
  { id: 'coming_soon', pattern: /\bcoming soon\b/i },
  { id: 'under_construction', pattern: /\bunder construction\b/i },
  { id: 'placeholder', pattern: /\bplaceholder\b/i },
  { id: 'match_kernel', pattern: /\bmatch kernel\b/i },
  { id: 'source_snapshot_hash', pattern: /\bsource_snapshot_hash\b/i },
  { id: 'semantic_truth_hash_construction', pattern: /semantic truth hash construction/i },
  { id: 'artifact_hash_construction', pattern: /artifact hash construction/i },
  { id: 'bayesian_internals', pattern: /Bayesian model internals/i },
  { id: 'exact_matching_threshold', pattern: /exact matching threshold/i },
];

/** Required visible section markers on /methodology (public proof page). */
export const D6B_METHODOLOGY_REQUIRED_MARKERS = [
  'Bottom Line Up Front',
  'Five things that are true about this methodology',
  'How deterministic reconciliation works',
  'What counts as verified evidence',
  'What attribution models prove',
  'How discrepancies are classified',
  'How delayed evidence is handled',
  'How confidence is expressed',
  'Why LLMs do not compute financial truth',
  'Limitations',
  'Last updated',
];

export const D6B_METHODOLOGY_REQUIRED_LINKS = [
  '/revenue-verification',
  '/attribution-methodology',
  '/discrepancy-taxonomy',
  '/ai-boundary',
];

/**
 * @param {string} html
 * @returns {string[]}
 */
export function validateD6MethodologyExposure(html) {
  const errors = [];
  if (!html || html.length < 1200) {
    errors.push(`${D6B_METHODOLOGY_ROUTE}: HTML unexpectedly short`);
    return errors;
  }

  const lower = html.toLowerCase();

  for (const { id, pattern } of D6B_METHODOLOGY_FORBIDDEN_REGEXES) {
    if (pattern.test(html)) {
      errors.push(`${D6B_METHODOLOGY_ROUTE}: forbidden D6-b pattern "${id}"`);
    }
  }

  for (const marker of D6B_METHODOLOGY_REQUIRED_MARKERS) {
    if (!html.includes(marker) && !lower.includes(marker.toLowerCase())) {
      errors.push(`${D6B_METHODOLOGY_ROUTE}: missing required marker "${marker}"`);
    }
  }

  for (const href of D6B_METHODOLOGY_REQUIRED_LINKS) {
    if (!html.includes(`href="${href}"`) && !html.includes(`href='${href}'`)) {
      errors.push(`${D6B_METHODOLOGY_ROUTE}: missing proof link ${href}`);
    }
  }

  if (!/<h1[\s>]/i.test(html)) {
    errors.push(`${D6B_METHODOLOGY_ROUTE}: missing <h1>`);
  }

  return errors;
}
