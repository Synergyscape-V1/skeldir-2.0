import type { FirstTrustEnvelopeSummary } from './types';
import type { AuthorityClass, PolicyAuthorityState } from '../lib/types';

/** Hard byte budget for Step 5 summary transport — full payloads must fail closed */
export const MAX_SUMMARY_PAYLOAD_BYTES = 8192;

export const FORBIDDEN_SUMMARY_FIELDS = [
  'rawEnvelope',
  'fullEnvelope',
  'envelopeJson',
  'trustEnvelopeJson',
  'signedPayload',
  'rawSignedPayload',
  'artifactPayload',
  'rawArtifact',
  'rawClaims',
  'rawAttributionGraph',
  'verificationMaterial',
  'signatureVerificationPayload',
  'semanticTruthHash',
  'artifactHash',
  'signatureHash',
  'provenanceChain',
  'jsonContract',
  'auditSignature',
  'ledgerDetail',
  'claimDetail',
  'exportPayload',
  'apiResponse',
] as const;

const ALLOWED_SUMMARY_KEYS = new Set([
  'envelopeId',
  'subjectRef',
  'verifiedRevenueMinor',
  'currencyCode',
  'revenueAuthority',
  'attributionModel',
  'attributionAuthority',
  'confidenceStatus',
  'confidenceAuthority',
  'confidenceReason',
  'confidenceMethodOrContext',
  'intervalLower',
  'intervalUpper',
  'credibleInterval',
  'uncertaintyBand',
  'qualitativeProbabilisticState',
  'sampleOrSourceContext',
  'benchmarkStatus',
  'benchmarkReason',
  'policyAuthority',
  'auditEventId',
  'generatedAt',
]);

export type SummaryValidationFailure =
  | 'schema_invalid'
  | 'payload_oversized'
  | 'forbidden_fields'
  | 'naked_scalar_confidence';

export type SummaryValidationResult =
  | { ok: true; summary: FirstTrustEnvelopeSummary; byteSize: number }
  | { ok: false; failure: SummaryValidationFailure; message: string };

export function measureSerializedPayloadBytes(input: unknown): number {
  const serialized = JSON.stringify(input, (_key, value) =>
    typeof value === 'bigint' ? value.toString() : value,
  );
  return new TextEncoder().encode(serialized).byteLength;
}

export function detectForbiddenSummaryFields(input: unknown): string[] {
  if (!input || typeof input !== 'object' || Array.isArray(input)) return [];
  return FORBIDDEN_SUMMARY_FIELDS.filter((field) =>
    Object.prototype.hasOwnProperty.call(input, field),
  );
}

export function hasProbabilisticConfidenceShape(summary: FirstTrustEnvelopeSummary): boolean {
  if (summary.confidenceStatus === 'unavailable' || summary.confidenceStatus === 'delayed') {
    return Boolean(summary.confidenceReason);
  }
  if (summary.confidenceStatus !== 'available') return false;

  const hasInterval =
    summary.intervalLower !== undefined ||
    summary.intervalUpper !== undefined ||
    Boolean(summary.credibleInterval) ||
    Boolean(summary.uncertaintyBand) ||
    Boolean(summary.qualitativeProbabilisticState);

  const hasContext = Boolean(summary.confidenceMethodOrContext || summary.sampleOrSourceContext);

  return hasInterval && hasContext && Boolean(summary.confidenceReason);
}

export function isNakedScalarConfidence(summary: FirstTrustEnvelopeSummary): boolean {
  if (summary.confidenceStatus !== 'available') return false;
  return !hasProbabilisticConfidenceShape(summary);
}

function parseMinorUnits(value: unknown): bigint | null {
  if (typeof value === 'bigint') return value;
  if (typeof value === 'number' && Number.isInteger(value)) return BigInt(value);
  if (typeof value === 'string' && /^-?\d+$/.test(value)) return BigInt(value);
  return null;
}

export function normalizeSummaryInput(input: unknown): FirstTrustEnvelopeSummary | null {
  if (!input || typeof input !== 'object' || Array.isArray(input)) return null;
  const raw = input as Record<string, unknown>;

  const verifiedRevenueMinor = parseMinorUnits(raw.verifiedRevenueMinor);
  if (verifiedRevenueMinor === null) return null;
  if (typeof raw.envelopeId !== 'string' || typeof raw.subjectRef !== 'string') return null;
  if (typeof raw.currencyCode !== 'string' || typeof raw.attributionModel !== 'string') return null;
  if (typeof raw.auditEventId !== 'string' || typeof raw.generatedAt !== 'string') return null;
  if (typeof raw.policyAuthority !== 'string') return null;

  const confidenceStatus = raw.confidenceStatus;
  if (
    confidenceStatus !== 'available' &&
    confidenceStatus !== 'unavailable' &&
    confidenceStatus !== 'delayed'
  ) {
    return null;
  }

  return {
    envelopeId: raw.envelopeId,
    subjectRef: raw.subjectRef,
    verifiedRevenueMinor,
    currencyCode: raw.currencyCode,
    revenueAuthority: 'deterministic',
    attributionModel: raw.attributionModel,
    attributionAuthority: 'deterministic',
    confidenceStatus,
    confidenceAuthority:
      typeof raw.confidenceAuthority === 'string'
        ? (raw.confidenceAuthority as AuthorityClass)
        : undefined,
    confidenceReason: typeof raw.confidenceReason === 'string' ? raw.confidenceReason : undefined,
    confidenceMethodOrContext:
      typeof raw.confidenceMethodOrContext === 'string' ? raw.confidenceMethodOrContext : undefined,
    intervalLower: typeof raw.intervalLower === 'number' ? raw.intervalLower : undefined,
    intervalUpper: typeof raw.intervalUpper === 'number' ? raw.intervalUpper : undefined,
    credibleInterval: typeof raw.credibleInterval === 'string' ? raw.credibleInterval : undefined,
    uncertaintyBand: typeof raw.uncertaintyBand === 'string' ? raw.uncertaintyBand : undefined,
    qualitativeProbabilisticState:
      typeof raw.qualitativeProbabilisticState === 'string'
        ? raw.qualitativeProbabilisticState
        : undefined,
    sampleOrSourceContext:
      typeof raw.sampleOrSourceContext === 'string' ? raw.sampleOrSourceContext : undefined,
    benchmarkStatus:
      raw.benchmarkStatus === 'unavailable' || raw.benchmarkStatus === 'suppressed'
        ? raw.benchmarkStatus
        : undefined,
    benchmarkReason: typeof raw.benchmarkReason === 'string' ? raw.benchmarkReason : undefined,
    policyAuthority: raw.policyAuthority as PolicyAuthorityState,
    auditEventId: raw.auditEventId,
    generatedAt: raw.generatedAt,
  };
}

export function validateEnvelopeSummaryCore(summary: FirstTrustEnvelopeSummary): boolean {
  return Boolean(
    summary.envelopeId &&
      summary.subjectRef &&
      summary.auditEventId &&
      summary.revenueAuthority === 'deterministic' &&
      summary.policyAuthority,
  );
}

export function validateSummaryTransportBoundary(input: unknown): SummaryValidationResult {
  const forbidden = detectForbiddenSummaryFields(input);
  if (forbidden.length > 0) {
    return {
      ok: false,
      failure: 'forbidden_fields',
      message: `Forbidden full-payload fields rejected: ${forbidden.join(', ')}`,
    };
  }

  const byteSize = measureSerializedPayloadBytes(input);
  if (byteSize > MAX_SUMMARY_PAYLOAD_BYTES) {
    return {
      ok: false,
      failure: 'payload_oversized',
      message: `Summary payload exceeds ${MAX_SUMMARY_PAYLOAD_BYTES} byte budget`,
    };
  }

  const summary = normalizeSummaryInput(input);
  if (!summary || !validateEnvelopeSummaryCore(summary)) {
    return {
      ok: false,
      failure: 'schema_invalid',
      message: 'TrustEnvelope summary schema is incomplete or invalid',
    };
  }

  if (isNakedScalarConfidence(summary)) {
    return {
      ok: false,
      failure: 'naked_scalar_confidence',
      message: 'Confidence available without probabilistic interval or uncertainty shape',
    };
  }

  if (
    (summary.confidenceStatus === 'unavailable' || summary.confidenceStatus === 'delayed') &&
    !summary.confidenceReason
  ) {
    return {
      ok: false,
      failure: 'schema_invalid',
      message: 'Confidence unavailable or delayed requires reason copy',
    };
  }

  for (const key of Object.keys(input as object)) {
    if (!ALLOWED_SUMMARY_KEYS.has(key)) {
      return {
        ok: false,
        failure: 'schema_invalid',
        message: `Unexpected summary field rejected: ${key}`,
      };
    }
  }

  return { ok: true, summary, byteSize };
}

export function createOversizedSummaryFixture(): Record<string, unknown> {
  const base = createDefaultUnavailableSummary();
  return {
    ...base,
    verifiedRevenueMinor: base.verifiedRevenueMinor.toString(),
    padding: 'x'.repeat(MAX_SUMMARY_PAYLOAD_BYTES),
  };
}

export function createDefaultUnavailableSummary(): FirstTrustEnvelopeSummary {
  return {
    envelopeId: 'trust_envelope_01',
    subjectRef: 'commerce_event_01',
    verifiedRevenueMinor: 125000n,
    currencyCode: 'USD',
    revenueAuthority: 'deterministic',
    attributionModel: 'last_touch',
    attributionAuthority: 'deterministic',
    confidenceStatus: 'unavailable',
    confidenceAuthority: 'unavailable',
    confidenceReason: 'Confidence is unavailable. Deterministic verification remains active.',
    benchmarkStatus: 'unavailable',
    benchmarkReason: 'No defensible benchmark exists for this segment yet.',
    policyAuthority: 'blocked',
    auditEventId: 'aud_te_001',
    generatedAt: new Date().toISOString(),
  };
}

export function createAvailableConfidenceSummary(): FirstTrustEnvelopeSummary {
  return {
    ...createDefaultUnavailableSummary(),
    confidenceStatus: 'available',
    confidenceAuthority: 'probabilistic',
    confidenceReason: 'Bayesian posterior available for this commerce window.',
    confidenceMethodOrContext: 'tenant_longitudinal posterior fit',
    intervalLower: 0.12,
    intervalUpper: 0.18,
    credibleInterval: '12% – 18% posterior interval',
    uncertaintyBand: '±3pp uncertainty band',
    qualitativeProbabilisticState: 'moderate posterior certainty',
    sampleOrSourceContext: 'commerce_event_01 observation window',
  };
}
