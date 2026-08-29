/** Maps fixture envelope IDs to related claim detail routes (no /trust/* navigation). */
export function resolveClaimIdFromEnvelopeId(envelopeId: string): string | null {
  const match = /^env_(\d{4})$/.exec(envelopeId.trim());
  if (!match) return null;
  return `claim_${match[1]}`;
}

export function buildClaimTrustDrawerHref(envelopeId: string, focus?: string | null): string {
  const claimId = resolveClaimIdFromEnvelopeId(envelopeId);
  if (!claimId) return '/app/claims';
  const params = new URLSearchParams({ trustEnvelope: envelopeId });
  if (focus) params.set('trustFocus', focus);
  return `/app/claims/${claimId}?${params.toString()}`;
}
