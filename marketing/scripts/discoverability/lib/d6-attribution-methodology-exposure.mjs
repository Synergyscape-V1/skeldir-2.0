/**
 * D6-b — /attribution-methodology IP exposure and placeholder-theater checks.
 */

export const D6B_ATTRIBUTION_METHODOLOGY_ROUTE = '/attribution-methodology';

export const D6B_ATTRIBUTION_METHODOLOGY_FORBIDDEN_REGEXES = [
  { id: 'technical_disclosure_only_token', pattern: /\btechnical_disclosure_only\b/i },
  { id: 'legal_review_required_token', pattern: /\blegal_review_required\b/i },
  { id: 'owner_registry_slug', pattern: /Owner_Skeldir_Product_Engineering/i },
  { id: 'coming_soon', pattern: /\bcoming soon\b/i },
  { id: 'under_construction', pattern: /\bunder construction\b/i },
  { id: 'placeholder', pattern: /\bplaceholder\b/i },
  { id: 'draft', pattern: /\bdraft\b/i },
  { id: 'exact_attribution_formula', pattern: /\bexact attribution formula\b/i },
  { id: 'weighting_logic', pattern: /\bweighting logic\b/i },
  { id: 'decay_function', pattern: /\bdecay function\b/i },
  { id: 'model_parameter', pattern: /\bmodel parameter\b/i },
  { id: 'window_length_value', pattern: /\bwindow length value\b/i },
  { id: 'eligibility_rule_implementation', pattern: /\beligibility rule implementation\b/i },
  { id: 'exclusion_rule_implementation', pattern: /\bexclusion rule implementation\b/i },
  { id: 'touchpoint_identity_resolution', pattern: /\btouchpoint identity resolution\b/i },
  { id: 'policy_version_mechanics', pattern: /\bpolicy version mechanics\b/i },
  { id: 'recompute_procedure', pattern: /\brecompute procedure\b/i },
  { id: 'reproduce_model_output', pattern: /\breproduce the model output\b/i },
  { id: 'database_schema', pattern: /\bdatabase schema\b/i },
  { id: 'event_normalization', pattern: /\bevent normalization\b/i },
  { id: 'anti_gaming', pattern: /\banti-gaming\b/i },
  { id: 'anti_gaming_space', pattern: /\banti gaming\b/i },
  { id: 'named_model_catalog_first_touch', pattern: /\bfirst-touch\b/i },
  { id: 'named_model_catalog_last_touch', pattern: /\blast-touch\b/i },
  { id: 'named_model_catalog_time_decay', pattern: /\btime-decay\b/i },
  { id: 'named_model_catalog_data_driven', pattern: /\bdata-driven\b/i },
  { id: 'named_assumption_contract_window_length', pattern: /\bwindow length\b/i },
  { id: 'named_assumption_contract_eligibility_rules', pattern: /\beligibility rules\b/i },
  { id: 'references_underlying_deterministic', pattern: /references the underlying deterministic/i },
];

export const D6B_ATTRIBUTION_METHODOLOGY_REQUIRED_MARKERS = [
  'Attribution Methodology',
  'Key facts',
  'What attribution models answer',
  'What assumptions mean',
  'Why attribution models are bounded',
  'Why attribution is not causality',
  'How attribution output relates to deterministic revenue',
  'Current limitations',
  'Last updated',
];

export const D6B_ATTRIBUTION_METHODOLOGY_SEPARATION_MARKERS = [
  'verified revenue',
  'deterministic',
  'model-derived',
  'distributes credit',
  'causal lift',
  'controlled experimentation',
  'incrementality',
];

export const D6B_ATTRIBUTION_METHODOLOGY_REQUIRED_LINKS = [
  '/methodology',
  '/revenue-verification',
  '/discrepancy-taxonomy',
  '/ai-boundary',
  '/trust-envelope',
];

export const D6B_ATTRIBUTION_METHODOLOGY_BOUNDARY_MARKERS = [
  'confused with verified revenue',
  'causal lift',
  'informational',
  'does not replace contractual terms',
];

/**
 * @param {string} html
 * @returns {string[]}
 */
export function validateD6AttributionMethodologyExposure(html) {
  const errors = [];
  if (!html || html.length < 1200) {
    errors.push(`${D6B_ATTRIBUTION_METHODOLOGY_ROUTE}: HTML unexpectedly short`);
    return errors;
  }

  const lower = html.toLowerCase();

  for (const { id, pattern } of D6B_ATTRIBUTION_METHODOLOGY_FORBIDDEN_REGEXES) {
    if (pattern.test(html)) {
      errors.push(`${D6B_ATTRIBUTION_METHODOLOGY_ROUTE}: forbidden D6-b pattern "${id}"`);
    }
  }

  for (const marker of D6B_ATTRIBUTION_METHODOLOGY_REQUIRED_MARKERS) {
    if (!html.includes(marker) && !lower.includes(marker.toLowerCase())) {
      errors.push(`${D6B_ATTRIBUTION_METHODOLOGY_ROUTE}: missing required marker "${marker}"`);
    }
  }

  for (const marker of D6B_ATTRIBUTION_METHODOLOGY_SEPARATION_MARKERS) {
    if (!html.includes(marker) && !lower.includes(marker.toLowerCase())) {
      errors.push(`${D6B_ATTRIBUTION_METHODOLOGY_ROUTE}: missing separation marker "${marker}"`);
    }
  }

  for (const href of D6B_ATTRIBUTION_METHODOLOGY_REQUIRED_LINKS) {
    if (!html.includes(`href="${href}"`) && !html.includes(`href='${href}'`)) {
      errors.push(`${D6B_ATTRIBUTION_METHODOLOGY_ROUTE}: missing proof link ${href}`);
    }
  }

  const boundaryOk = D6B_ATTRIBUTION_METHODOLOGY_BOUNDARY_MARKERS.some(
    (m) => html.includes(m) || lower.includes(m.toLowerCase()),
  );
  if (!boundaryOk) {
    errors.push(
      `${D6B_ATTRIBUTION_METHODOLOGY_ROUTE}: missing public attribution / revenue / causality boundary`,
    );
  }

  if (!/<h1[\s>]/i.test(html)) {
    errors.push(`${D6B_ATTRIBUTION_METHODOLOGY_ROUTE}: missing <h1>`);
  }

  if (/Loading\.\.\.|animate-pulse|Redirecting/i.test(html)) {
    errors.push(`${D6B_ATTRIBUTION_METHODOLOGY_ROUTE}: loading shell or redirect detected`);
  }

  return errors;
}
