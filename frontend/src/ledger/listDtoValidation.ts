/** Forbidden fields that must not appear in Level 7 list/index DTOs */
export const FORBIDDEN_LIST_ENVELOPE_FIELDS = [
  'fullEnvelope',
  'envelopeJson',
  'signedPayload',
  'artifactPayload',
  'verificationMaterial',
  'rawAttributionGraph',
  'provenanceChain',
  'jsonContract',
  'auditSignature',
  'semanticTruthHash',
  'artifactHash',
  'signatureHash',
  'canonicalPayload',
] as const;

export const FORBIDDEN_LIST_CLAIM_FIELDS = [
  'rawClaimPayload',
  'evidenceTimeline',
  'attributionGraph',
  'fullClaimDetail',
] as const;

export function detectForbiddenListFields(
  payload: unknown,
  forbidden: readonly string[],
): string[] {
  if (!payload || typeof payload !== 'object') return [];
  const found: string[] = [];
  const walk = (obj: Record<string, unknown>, prefix = '') => {
    for (const [key, value] of Object.entries(obj)) {
      const path = prefix ? `${prefix}.${key}` : key;
      if (forbidden.includes(key)) found.push(path);
      if (value && typeof value === 'object' && !Array.isArray(value)) {
        walk(value as Record<string, unknown>, path);
      }
    }
  };
  walk(payload as Record<string, unknown>);
  return found;
}

export function validateListDtoBoundary(
  payload: unknown,
  forbidden: readonly string[],
): { ok: true } | { ok: false; fields: string[] } {
  const fields = detectForbiddenListFields(payload, forbidden);
  if (fields.length > 0) return { ok: false, fields };
  return { ok: true };
}

export function measureListPayloadBytes(payload: unknown): number {
  return new TextEncoder().encode(JSON.stringify(payload, (_, v) =>
    typeof v === 'bigint' ? v.toString() : v,
  )).length;
}

export const MAX_LIST_ROW_PAYLOAD_BYTES = 4096;
