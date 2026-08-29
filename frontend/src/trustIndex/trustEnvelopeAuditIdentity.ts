export const DEFAULT_SYNTHETIC_TRUST_ENVELOPE_COUNT = 246;

export function buildSyntheticTrustEnvelopeId(index: number): string {
  return `env_${String(index + 1).padStart(4, '0')}`;
}

export function buildSyntheticTrustEnvelopeAuditEventId(index: number): string {
  return `evt_trust_envelope_${String(index + 1).padStart(4, '0')}`;
}
