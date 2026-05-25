/**
 * D6-b — /security IP exposure, overclaim, and placeholder-theater checks.
 */

export const D6B_SECURITY_ROUTE = '/security';

export const D6B_SECURITY_FORBIDDEN_IMPLEMENTATION_REGEXES = [
  { id: 'rls', pattern: /\bRLS\b/ },
  { id: 'guc', pattern: /\bGUC\b/ },
  { id: 'row_level_security', pattern: /\brow-level security\b/i },
  { id: 'set_local', pattern: /\bSET LOCAL\b/i },
  { id: 'session_variable', pattern: /\bsession variable\b/i },
  { id: 'database_schema', pattern: /\bdatabase schema\b/i },
  { id: 'tenant_id_column', pattern: /\btenant_id column\b/i },
  { id: 'worker_isolation', pattern: /\bworker isolation\b/i },
  { id: 'encryption_key', pattern: /\bencryption key\b/i },
  { id: 'kms', pattern: /\bKMS\b/ },
  { id: 'key_rotation', pattern: /\bkey rotation\b/i },
  { id: 'ingestion_middleware', pattern: /\bingestion middleware\b/i },
  { id: 'pii_stripping_middleware', pattern: /\bPII stripping middleware\b/i },
  { id: 'hashing_algorithm', pattern: /\bhashing algorithm\b/i },
  { id: 'signing_algorithm', pattern: /\bsigning algorithm\b/i },
  { id: 'audit_log_schema', pattern: /\baudit log schema\b/i },
  { id: 'state_transition_table', pattern: /\bstate transition table\b/i },
  { id: 'network_topology', pattern: /\bnetwork topology\b/i },
  { id: 'security_group', pattern: /\bsecurity group\b/i },
  { id: 'waf_rule', pattern: /\bWAF rule\b/i },
  { id: 'penetration_test_result', pattern: /\bpenetration test result\b/i },
  { id: 'vulnerability_detail', pattern: /\bvulnerability detail\b/i },
];

export const D6B_SECURITY_FORBIDDEN_OVERCLAIM_REGEXES = [
  { id: 'soc2_certified', pattern: /\bSOC 2 certified\b/i },
  { id: 'iso_certified', pattern: /\bISO 27001 certified\b/i },
  { id: 'hipaa_compliant', pattern: /\bHIPAA compliant\b/i },
  { id: 'pci_compliant', pattern: /\bPCI compliant\b/i },
  { id: 'gdpr_compliant', pattern: /\bGDPR compliant\b/i },
  { id: 'ccpa_compliant', pattern: /\bCCPA compliant\b/i },
  { id: 'zero_pii', pattern: /\bzero PII\b/i },
  { id: 'no_pii', pattern: /\bno PII\b/i },
  { id: 'guaranteed_cross_tenant', pattern: /\bguaranteed cross-tenant\b/i },
  { id: 'unbreakable', pattern: /\bunbreakable\b/i },
  { id: 'fully_secure', pattern: /\bfully secure\b/i },
  { id: 'bank_grade', pattern: /\bbank-grade\b/i },
  { id: 'military_grade', pattern: /\bmilitary-grade\b/i },
];

export const D6B_SECURITY_FORBIDDEN_PLACEHOLDER_REGEXES = [
  { id: 'technical_disclosure_only_token', pattern: /\btechnical_disclosure_only\b/i },
  { id: 'legal_review_required_token', pattern: /\blegal_review_required\b/i },
  { id: 'owner_registry_slug', pattern: /Owner_Skeldir_Product_Engineering/i },
  { id: 'coming_soon', pattern: /\bcoming soon\b/i },
  { id: 'under_construction', pattern: /\bunder construction\b/i },
  { id: 'placeholder', pattern: /\bplaceholder\b/i },
  { id: 'draft', pattern: /\bdraft\b/i },
];

export const D6B_SECURITY_REQUIRED_MARKERS = [
  'Security',
  'Key facts',
  'Security posture principles',
  'Tenant isolation',
  'Sensitive data handling',
  'Financial value precision',
  'Auditability',
  'Security inquiries',
  'Current limitations',
  'Last updated',
];

export const D6B_SECURITY_CONTROLLED_DISCLOSURE_MARKERS = [
  'security documentation',
  'procurement',
  'vulnerability',
  'security@skeldir.com',
  'controlled',
  'direct security',
];

export const D6B_SECURITY_REQUIRED_LINKS = [
  '/methodology',
  '/revenue-verification',
  '/trust-envelope',
  '/ai-boundary',
  '/privacy',
  '/api',
  '/docs',
];

export const D6B_SECURITY_PUBLIC_BOUNDARY_MARKERS = [
  'public security posture',
  'direct security engagement',
  'controlled',
];

/**
 * @param {string} html
 * @returns {string[]}
 */
export function validateD6SecurityExposure(html) {
  const errors = [];
  if (!html || html.length < 1200) {
    errors.push(`${D6B_SECURITY_ROUTE}: HTML unexpectedly short`);
    return errors;
  }

  const lower = html.toLowerCase();

  for (const { id, pattern } of [
    ...D6B_SECURITY_FORBIDDEN_IMPLEMENTATION_REGEXES,
    ...D6B_SECURITY_FORBIDDEN_OVERCLAIM_REGEXES,
    ...D6B_SECURITY_FORBIDDEN_PLACEHOLDER_REGEXES,
  ]) {
    if (pattern.test(html)) {
      errors.push(`${D6B_SECURITY_ROUTE}: forbidden D6-b pattern "${id}"`);
    }
  }

  for (const marker of D6B_SECURITY_REQUIRED_MARKERS) {
    if (!html.includes(marker) && !lower.includes(marker.toLowerCase())) {
      errors.push(`${D6B_SECURITY_ROUTE}: missing required marker "${marker}"`);
    }
  }

  for (const marker of D6B_SECURITY_CONTROLLED_DISCLOSURE_MARKERS) {
    if (!html.includes(marker) && !lower.includes(marker.toLowerCase())) {
      errors.push(`${D6B_SECURITY_ROUTE}: missing controlled-disclosure marker "${marker}"`);
    }
  }

  for (const href of D6B_SECURITY_REQUIRED_LINKS) {
    if (!html.includes(`href="${href}"`) && !html.includes(`href='${href}'`)) {
      errors.push(`${D6B_SECURITY_ROUTE}: missing proof link ${href}`);
    }
  }

  const boundaryOk = D6B_SECURITY_PUBLIC_BOUNDARY_MARKERS.some(
    (m) => html.includes(m) || lower.includes(m.toLowerCase()),
  );
  if (!boundaryOk) {
    errors.push(`${D6B_SECURITY_ROUTE}: missing public security posture boundary`);
  }

  if (!/<h1[\s>]/i.test(html)) {
    errors.push(`${D6B_SECURITY_ROUTE}: missing <h1>`);
  }

  if (/Loading\.\.\.|animate-pulse|Redirecting/i.test(html)) {
    errors.push(`${D6B_SECURITY_ROUTE}: loading shell or redirect detected`);
  }

  return errors;
}
