/**
 * D6-b — /trust-envelope IP exposure and placeholder-theater checks.
 */

export const D6B_TRUST_ENVELOPE_ROUTE = '/trust-envelope';

/** Fatal: implementation leakage or internal registry tokens in public HTML. */
export const D6B_TRUST_ENVELOPE_FORBIDDEN_REGEXES = [
  { id: 'technical_disclosure_only_token', pattern: /\btechnical_disclosure_only\b/i },
  { id: 'legal_review_required_token', pattern: /\blegal_review_required\b/i },
  { id: 'operator_approved_token', pattern: /\boperator_approved\b/i },
  { id: 'owner_registry_slug', pattern: /Owner_Skeldir_Product_Engineering/i },
  { id: 'coming_soon', pattern: /\bcoming soon\b/i },
  { id: 'under_construction', pattern: /\bunder construction\b/i },
  { id: 'placeholder', pattern: /\bplaceholder\b/i },
  { id: 'draft', pattern: /\bdraft\b/i },
  { id: 'serialized_envelope', pattern: /\bserialized envelope\b/i },
  { id: 'byte_level_hash', pattern: /\bbyte-level hash\b/i },
  { id: 'byte_level_hash_alt', pattern: /\bbyte level hash\b/i },
  { id: 'normalized_claim_recipe', pattern: /normalized claim plus/i },
  { id: 'evidence_reference_set_recipe', pattern: /evidence reference set/i },
  { id: 'exact_enum', pattern: /\bexact enum\b/i },
  { id: 'replay_algorithm', pattern: /\breplay algorithm\b/i },
  { id: 'can_be_replayed', pattern: /\bcan be replayed\b/i },
  { id: 'payload_schema', pattern: /\bpayload schema\b/i },
  { id: 'field_schema', pattern: /\bfield schema\b/i },
  { id: 'trust_envelope_json', pattern: /TrustEnvelope JSON/i },
  { id: 'source_snapshot_hash', pattern: /\bsource_snapshot_hash\b/i },
  { id: 'match_kernel', pattern: /\bmatch kernel\b/i },
  { id: 'policy_version_computation', pattern: /policy version computation/i },
  { id: 'hash_construction', pattern: /\bhash construction\b/i },
  { id: 'semantic_truth_hash_algorithm', pattern: /semantic truth hash algorithm/i },
  { id: 'artifact_hash_algorithm', pattern: /artifact hash algorithm/i },
  { id: 'content_addressable', pattern: /\bcontent-addressable\b/i },
];

/** Required visible markers (concept-level proof page). */
export const D6B_TRUST_ENVELOPE_REQUIRED_MARKERS = [
  'TrustEnvelope',
  'Key facts',
  'What is a TrustEnvelope',
  'Deterministic values',
  'provenance chain',
  'semantic truth hash',
  'artifact hash',
  'Confidence status',
  'Benchmark metadata',
  'Policy authority',
  'Fallback reason',
  'External verification metadata',
  'Action authority',
  'Audit trail',
  'Limitations',
  'Last updated',
];

export const D6B_TRUST_ENVELOPE_REQUIRED_LINKS = [
  '/methodology',
  '/revenue-verification',
  '/attribution-methodology',
  '/discrepancy-taxonomy',
  '/ai-boundary',
  '/api',
  '/docs',
];

/** Designed absence — public API boundary must be stated professionally. */
export const D6B_TRUST_ENVELOPE_API_BOUNDARY_MARKERS = [
  'does not promise a live public API',
  'documented separately',
];

/**
 * @param {string} html
 * @returns {string[]}
 */
export function validateD6TrustEnvelopeExposure(html) {
  const errors = [];
  if (!html || html.length < 1500) {
    errors.push(`${D6B_TRUST_ENVELOPE_ROUTE}: HTML unexpectedly short`);
    return errors;
  }

  const lower = html.toLowerCase();

  for (const { id, pattern } of D6B_TRUST_ENVELOPE_FORBIDDEN_REGEXES) {
    if (pattern.test(html)) {
      errors.push(`${D6B_TRUST_ENVELOPE_ROUTE}: forbidden D6-b pattern "${id}"`);
    }
  }

  for (const marker of D6B_TRUST_ENVELOPE_REQUIRED_MARKERS) {
    if (!html.includes(marker) && !lower.includes(marker.toLowerCase())) {
      errors.push(`${D6B_TRUST_ENVELOPE_ROUTE}: missing required marker "${marker}"`);
    }
  }

  for (const href of D6B_TRUST_ENVELOPE_REQUIRED_LINKS) {
    if (!html.includes(`href="${href}"`) && !html.includes(`href='${href}'`)) {
      errors.push(`${D6B_TRUST_ENVELOPE_ROUTE}: missing proof link ${href}`);
    }
  }

  const apiBoundaryOk = D6B_TRUST_ENVELOPE_API_BOUNDARY_MARKERS.some(
    (m) => html.includes(m) || lower.includes(m.toLowerCase()),
  );
  if (!apiBoundaryOk) {
    errors.push(
      `${D6B_TRUST_ENVELOPE_ROUTE}: missing public API boundary (live public API / documented separately)`,
    );
  }

  if (!/<h1[\s>]/i.test(html)) {
    errors.push(`${D6B_TRUST_ENVELOPE_ROUTE}: missing <h1>`);
  }

  if (/Loading\.\.\.|animate-pulse|Redirecting/i.test(html)) {
    errors.push(`${D6B_TRUST_ENVELOPE_ROUTE}: loading shell or redirect detected`);
  }

  return errors;
}
