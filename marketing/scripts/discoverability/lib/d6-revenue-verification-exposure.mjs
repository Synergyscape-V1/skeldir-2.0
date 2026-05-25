/**
 * D6-b — /revenue-verification IP exposure and placeholder-theater checks.
 */

export const D6B_REVENUE_VERIFICATION_ROUTE = '/revenue-verification';

export const D6B_REVENUE_VERIFICATION_FORBIDDEN_REGEXES = [
  { id: 'technical_disclosure_only_token', pattern: /\btechnical_disclosure_only\b/i },
  { id: 'legal_review_required_token', pattern: /\blegal_review_required\b/i },
  { id: 'owner_registry_slug', pattern: /Owner_Skeldir_Product_Engineering/i },
  { id: 'coming_soon', pattern: /\bcoming soon\b/i },
  { id: 'under_construction', pattern: /\bunder construction\b/i },
  { id: 'placeholder', pattern: /\bplaceholder\b/i },
  { id: 'draft', pattern: /\bdraft\b/i },
  { id: 'three_joined_streams', pattern: /\bthree joined streams\b/i },
  { id: 'shared_time_window', pattern: /\bshared time window\b/i },
  { id: 'shared_identity_key', pattern: /\bshared identity key\b/i },
  { id: 'identity_key', pattern: /\bidentity key\b/i },
  { id: 'customer_identifiers', pattern: /\bcustomer identifiers\b/i },
  { id: 'matching_payment_record', pattern: /\bmatching payment record\b/i },
  { id: 'match_kernel', pattern: /\bmatch kernel\b/i },
  { id: 'join_logic', pattern: /\bjoin logic\b/i },
  { id: 'matching_threshold', pattern: /\bmatching threshold\b/i },
  { id: 'reconciliation_kernel', pattern: /\breconciliation kernel\b/i },
  { id: 'field_mapping', pattern: /\bfield mapping\b/i },
  { id: 'source_normalization_procedure', pattern: /\bsource normalization procedure\b/i },
  { id: 'processor_specific_matching', pattern: /processor-specific matching/i },
  { id: 'database_schema', pattern: /\bdatabase schema\b/i },
  { id: 'worker_pipeline', pattern: /\bworker pipeline\b/i },
  { id: 'exact_state_transition', pattern: /\bexact state transition\b/i },
];

export const D6B_REVENUE_VERIFICATION_REQUIRED_MARKERS = [
  'Revenue Verification',
  'Key facts',
  'Why platform-reported revenue',
  'Commerce evidence',
  'Payment evidence',
  'How Skeldir verifies revenue',
  'How discrepancies are handled',
  'Delayed evidence',
  'What revenue verification proves',
  'What revenue verification does not prove',
  'Operational limitations',
  'Last updated',
];

export const D6B_REVENUE_VERIFICATION_REQUIRED_LINKS = [
  '/methodology',
  '/discrepancy-taxonomy',
  '/attribution-methodology',
  '/ai-boundary',
  '/trust-envelope',
];

export const D6B_REVENUE_VERIFICATION_BOUNDARY_MARKERS = [
  'informational',
  'does not replace contractual terms',
  'not a contractual guarantee',
];

/**
 * @param {string} html
 * @returns {string[]}
 */
export function validateD6RevenueVerificationExposure(html) {
  const errors = [];
  if (!html || html.length < 1200) {
    errors.push(`${D6B_REVENUE_VERIFICATION_ROUTE}: HTML unexpectedly short`);
    return errors;
  }

  const lower = html.toLowerCase();

  for (const { id, pattern } of D6B_REVENUE_VERIFICATION_FORBIDDEN_REGEXES) {
    if (pattern.test(html)) {
      errors.push(`${D6B_REVENUE_VERIFICATION_ROUTE}: forbidden D6-b pattern "${id}"`);
    }
  }

  for (const marker of D6B_REVENUE_VERIFICATION_REQUIRED_MARKERS) {
    if (!html.includes(marker) && !lower.includes(marker.toLowerCase())) {
      errors.push(`${D6B_REVENUE_VERIFICATION_ROUTE}: missing required marker "${marker}"`);
    }
  }

  for (const href of D6B_REVENUE_VERIFICATION_REQUIRED_LINKS) {
    if (!html.includes(`href="${href}"`) && !html.includes(`href='${href}'`)) {
      errors.push(`${D6B_REVENUE_VERIFICATION_ROUTE}: missing proof link ${href}`);
    }
  }

  const boundaryOk = D6B_REVENUE_VERIFICATION_BOUNDARY_MARKERS.some(
    (m) => html.includes(m) || lower.includes(m.toLowerCase()),
  );
  if (!boundaryOk) {
    errors.push(
      `${D6B_REVENUE_VERIFICATION_ROUTE}: missing informational / non-contract boundary`,
    );
  }

  if (!/<h1[\s>]/i.test(html)) {
    errors.push(`${D6B_REVENUE_VERIFICATION_ROUTE}: missing <h1>`);
  }

  if (/Loading\.\.\.|animate-pulse|Redirecting/i.test(html)) {
    errors.push(`${D6B_REVENUE_VERIFICATION_ROUTE}: loading shell or redirect detected`);
  }

  return errors;
}
