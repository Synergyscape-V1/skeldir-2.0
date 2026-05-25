/**
 * D6-b — /discrepancy-taxonomy IP exposure and placeholder-theater checks.
 */

export const D6B_DISCREPANCY_TAXONOMY_ROUTE = '/discrepancy-taxonomy';

export const D6B_DISCREPANCY_TAXONOMY_FORBIDDEN_REGEXES = [
  { id: 'technical_disclosure_only_token', pattern: /\btechnical_disclosure_only\b/i },
  { id: 'legal_review_required_token', pattern: /\blegal_review_required\b/i },
  { id: 'owner_registry_slug', pattern: /Owner_Skeldir_Product_Engineering/i },
  { id: 'coming_soon', pattern: /\bcoming soon\b/i },
  { id: 'under_construction', pattern: /\bunder construction\b/i },
  { id: 'placeholder', pattern: /\bplaceholder\b/i },
  { id: 'draft', pattern: /\bdraft\b/i },
  { id: 'defined_evidence_signature', pattern: /\bdefined evidence signature\b/i },
  { id: 'evidence_signature', pattern: /\bevidence signature\b/i },
  { id: 'specific_pattern', pattern: /\bspecific pattern\b/i },
  { id: 'triggers_each_classification', pattern: /\btriggers each classification\b/i },
  { id: 'trigger_logic', pattern: /\btrigger logic\b/i },
  { id: 'classification_criteria', pattern: /\bclassification criteria\b/i },
  { id: 'matching_rules', pattern: /\bmatching rules\b/i },
  { id: 'alignment_algorithm', pattern: /\balignment algorithm\b/i },
  { id: 'aligns_them_under', pattern: /\baligns them under\b/i },
  { id: 'normalizes_both_sides', pattern: /\bnormalizes both sides\b/i },
  { id: 'deduplicates_against', pattern: /\bdeduplicates against\b/i },
  { id: 'commerce_identifier', pattern: /\bcommerce identifier\b/i },
  { id: 'conversion_identifier', pattern: /\bconversion identifier\b/i },
  { id: 'conversion id', pattern: /\bconversion id\b/i },
  { id: 'operator_policy_assignment', pattern: /\boperator policy assignment\b/i },
  { id: 'assigns the conversion under', pattern: /\bassigns the conversion under\b/i },
  { id: 'candidate_classification_ranking', pattern: /\bcandidate classification ranking\b/i },
  { id: 'candidate_classifications', pattern: /\bcandidate classifications\b/i },
  { id: 'state_transition_logic', pattern: /\bstate transition logic\b/i },
  { id: 'field_mapping', pattern: /\bfield mapping\b/i },
  { id: 'database_schema', pattern: /\bdatabase schema\b/i },
  { id: 'processor_specific_matching', pattern: /processor-specific matching/i },
  { id: 'anti_gaming', pattern: /\banti-gaming\b/i },
  { id: 'anti_gaming_space', pattern: /\banti gaming\b/i },
  { id: 'policy_authority', pattern: /\bpolicy authority\b/i },
  { id: 'fallback_reason', pattern: /\bfallback reason\b/i },
  { id: 'benchmark_metadata', pattern: /\bbenchmark metadata\b/i },
];

export const D6B_DISCREPANCY_TAXONOMY_REQUIRED_MARKERS = [
  'Discrepancy Taxonomy',
  'Key facts',
  'Timing mismatch',
  'Currency, tax, or shipping mismatch',
  'Refund and chargeback adjustment',
  'Attribution-window mismatch',
  'Duplicate or order-reference mismatch',
  'Missing commerce evidence',
  'Unmatched platform claim',
  'Delayed arrival',
  'Current limitations',
  'Last updated',
];

export const D6B_DISCREPANCY_TAXONOMY_CLASS_MARKERS = [
  'timing mismatch',
  'currency',
  'tax',
  'shipping',
  'refund',
  'chargeback',
  'attribution-window',
  'duplicate',
  'missing commerce',
  'unmatched platform',
  'delayed arrival',
];

export const D6B_DISCREPANCY_TAXONOMY_REQUIRED_LINKS = [
  '/methodology',
  '/revenue-verification',
  '/attribution-methodology',
  '/ai-boundary',
  '/trust-envelope',
];

export const D6B_DISCREPANCY_TAXONOMY_BOUNDARY_MARKERS = [
  'informational',
  'does not replace contractual terms',
  'classified by type',
  'does not erase, average, or guess',
];

/**
 * @param {string} html
 * @returns {string[]}
 */
export function validateD6DiscrepancyTaxonomyExposure(html) {
  const errors = [];
  if (!html || html.length < 1200) {
    errors.push(`${D6B_DISCREPANCY_TAXONOMY_ROUTE}: HTML unexpectedly short`);
    return errors;
  }

  const lower = html.toLowerCase();

  for (const { id, pattern } of D6B_DISCREPANCY_TAXONOMY_FORBIDDEN_REGEXES) {
    if (pattern.test(html)) {
      errors.push(`${D6B_DISCREPANCY_TAXONOMY_ROUTE}: forbidden D6-b pattern "${id}"`);
    }
  }

  for (const marker of D6B_DISCREPANCY_TAXONOMY_REQUIRED_MARKERS) {
    if (!html.includes(marker) && !lower.includes(marker.toLowerCase())) {
      errors.push(`${D6B_DISCREPANCY_TAXONOMY_ROUTE}: missing required marker "${marker}"`);
    }
  }

  for (const marker of D6B_DISCREPANCY_TAXONOMY_CLASS_MARKERS) {
    if (!lower.includes(marker.toLowerCase())) {
      errors.push(`${D6B_DISCREPANCY_TAXONOMY_ROUTE}: missing class coverage marker "${marker}"`);
    }
  }

  for (const href of D6B_DISCREPANCY_TAXONOMY_REQUIRED_LINKS) {
    if (!html.includes(`href="${href}"`) && !html.includes(`href='${href}'`)) {
      errors.push(`${D6B_DISCREPANCY_TAXONOMY_ROUTE}: missing proof link ${href}`);
    }
  }

  const boundaryOk = D6B_DISCREPANCY_TAXONOMY_BOUNDARY_MARKERS.some(
    (m) => html.includes(m) || lower.includes(m.toLowerCase()),
  );
  if (!boundaryOk) {
    errors.push(
      `${D6B_DISCREPANCY_TAXONOMY_ROUTE}: missing public taxonomy / non-contract boundary`,
    );
  }

  if (!/<h1[\s>]/i.test(html)) {
    errors.push(`${D6B_DISCREPANCY_TAXONOMY_ROUTE}: missing <h1>`);
  }

  if (/Loading\.\.\.|animate-pulse|Redirecting/i.test(html)) {
    errors.push(`${D6B_DISCREPANCY_TAXONOMY_ROUTE}: loading shell or redirect detected`);
  }

  return errors;
}
