/**
 * D6-b — /ai-boundary IP exposure and placeholder-theater checks.
 */

export const D6B_AI_BOUNDARY_ROUTE = '/ai-boundary';

export const D6B_AI_BOUNDARY_FORBIDDEN_REGEXES = [
  { id: 'technical_disclosure_only_token', pattern: /\btechnical_disclosure_only\b/i },
  { id: 'legal_review_required_token', pattern: /\blegal_review_required\b/i },
  { id: 'owner_registry_slug', pattern: /Owner_Skeldir_Product_Engineering/i },
  { id: 'coming_soon', pattern: /\bcoming soon\b/i },
  { id: 'under_construction', pattern: /\bunder construction\b/i },
  { id: 'placeholder', pattern: /\bplaceholder\b/i },
  { id: 'draft', pattern: /\bdraft\b/i },
  { id: 'semantic_truth_hash', pattern: /\bsemantic truth hash\b/i },
  { id: 'template_version', pattern: /\btemplate version\b/i },
  { id: 'cache_key', pattern: /\bcache key\b/i },
  { id: 'signing_key_rotation', pattern: /\bsigning key rotation\b/i },
  { id: 'deterministic_match_verdict', pattern: /\bdeterministic match verdict\b/i },
  { id: 'integer_minor_units', pattern: /\binteger minor units\b/i },
  { id: 'trust_envelope_contract', pattern: /\bTrustEnvelope contract\b/i },
  { id: 'read_only_boundary', pattern: /\bread-only boundary\b/i },
  { id: 'deterministic_lookup', pattern: /\bdeterministic lookup\b/i },
  { id: 'design_partner_mode', pattern: /\bDesign Partner Mode\b/i },
  { id: 'simulation_only', pattern: /\bsimulation_only\b/i },
  { id: 'approval_required', pattern: /\bapproval_required\b/i },
  { id: 'auto_executable', pattern: /\bauto-executable\b/i },
  { id: 'owning_phase', pattern: /\bowning phase\b/i },
  { id: 'phase_closes', pattern: /\bphase closes\b/i },
  { id: 'policy_governed_externalization', pattern: /\bpolicy-governed externalization\b/i },
  { id: 'externalization_stages', pattern: /\bexternalization stages\b/i },
  { id: 'payload_schema', pattern: /\bpayload schema\b/i },
  { id: 'field_schema', pattern: /\bfield schema\b/i },
  { id: 'validation_pipeline', pattern: /\bvalidation pipeline\b/i },
  { id: 'action_authority', pattern: /\baction authority\b/i },
  { id: 'write access', pattern: /\bwrite access\b/i },
  { id: 'explanation_pipeline', pattern: /\bexplanation pipeline\b/i },
  { id: 'audit trail are passed', pattern: /\baudit trail are passed\b/i },
];

export const D6B_AI_BOUNDARY_REQUIRED_MARKERS = [
  'AI Boundary',
  'Bottom Line Up Front',
  'Key facts',
  'What LLMs do in Skeldir',
  'Why LLMs do not compute financial truth',
  'Deterministic grounding',
  'Bounded explanations',
  'Policy for AI agents consuming Skeldir',
  'Scope and trust boundary',
  'Current limitations',
  'Last updated',
];

export const D6B_AI_BOUNDARY_TRUTH_BOUNDARY_MARKERS = [
  'does not calculate',
  'authoritative',
  'advisory',
  'deterministic',
  'financial truth',
  'TrustEnvelope',
  'verification status',
];

export const D6B_AI_BOUNDARY_AGENT_MARKERS = [
  'agent',
  'authoritative',
  'advisory',
  'policy',
  'approval',
  'limitations',
];

export const D6B_AI_BOUNDARY_REQUIRED_LINKS = [
  '/methodology',
  '/trust-envelope',
  '/revenue-verification',
  '/attribution-methodology',
  '/discrepancy-taxonomy',
  '/api',
  '/docs',
];

export const D6B_AI_BOUNDARY_PUBLIC_BOUNDARY_MARKERS = [
  'public AI boundary',
  'documented separately',
  'does not calculate',
];

/**
 * @param {string} html
 * @returns {string[]}
 */
export function validateD6AiBoundaryExposure(html) {
  const errors = [];
  if (!html || html.length < 1200) {
    errors.push(`${D6B_AI_BOUNDARY_ROUTE}: HTML unexpectedly short`);
    return errors;
  }

  const lower = html.toLowerCase();

  for (const { id, pattern } of D6B_AI_BOUNDARY_FORBIDDEN_REGEXES) {
    if (pattern.test(html)) {
      errors.push(`${D6B_AI_BOUNDARY_ROUTE}: forbidden D6-b pattern "${id}"`);
    }
  }

  for (const marker of D6B_AI_BOUNDARY_REQUIRED_MARKERS) {
    if (!html.includes(marker) && !lower.includes(marker.toLowerCase())) {
      errors.push(`${D6B_AI_BOUNDARY_ROUTE}: missing required marker "${marker}"`);
    }
  }

  for (const marker of D6B_AI_BOUNDARY_TRUTH_BOUNDARY_MARKERS) {
    if (!html.includes(marker) && !lower.includes(marker.toLowerCase())) {
      errors.push(`${D6B_AI_BOUNDARY_ROUTE}: missing truth-boundary marker "${marker}"`);
    }
  }

  for (const marker of D6B_AI_BOUNDARY_AGENT_MARKERS) {
    if (!lower.includes(marker.toLowerCase())) {
      errors.push(`${D6B_AI_BOUNDARY_ROUTE}: missing agent-boundary marker "${marker}"`);
    }
  }

  for (const href of D6B_AI_BOUNDARY_REQUIRED_LINKS) {
    if (!html.includes(`href="${href}"`) && !html.includes(`href='${href}'`)) {
      errors.push(`${D6B_AI_BOUNDARY_ROUTE}: missing proof link ${href}`);
    }
  }

  const boundaryOk = D6B_AI_BOUNDARY_PUBLIC_BOUNDARY_MARKERS.some(
    (m) => html.includes(m) || lower.includes(m.toLowerCase()),
  );
  if (!boundaryOk) {
    errors.push(`${D6B_AI_BOUNDARY_ROUTE}: missing public AI boundary framing`);
  }

  if (!/<h1[\s>]/i.test(html)) {
    errors.push(`${D6B_AI_BOUNDARY_ROUTE}: missing <h1>`);
  }

  if (/Loading\.\.\.|animate-pulse|Redirecting/i.test(html)) {
    errors.push(`${D6B_AI_BOUNDARY_ROUTE}: loading shell or redirect detected`);
  }

  return errors;
}
