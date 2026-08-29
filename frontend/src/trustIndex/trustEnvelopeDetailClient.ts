import { getCurrentUserRole } from '../governance/governanceStore';
import { canViewTrustIndex } from '../ledger/permissions';
import { DETAIL_COPY } from '../detail/copy';
import { incrementDetailRequest, resetDetailRequestCounter } from '../detail/requestCounter';
import { validateTrustEnvelopeDetailDto } from '../detail/detailDtoValidation';
import type {
  TrustEnvelopeDetailDTO,
  TrustEnvelopeDetailOutcome,
  TrustEnvelopeAttributionData,
  TrustEnvelopeBenchmarkData,
  TrustEnvelopeConfidenceData,
  TrustEnvelopeDeterministicTruthData,
  TrustEnvelopePolicyAuthorityData,
  TrustEnvelopeSubjectData,
} from '../detail/types';
import { resolveTrustEnvelopeCanonicalId } from './trustEnvelopeDetailDisplay';

export type TrustDetailTestMode = 'default' | 'not_found';

let testMode: TrustDetailTestMode = 'default';

export function setTrustDetailTestMode(mode: TrustDetailTestMode): void {
  testMode = mode;
}

export function resetTrustDetailTestMode(): void {
  testMode = 'default';
}

const PRIMARY_FIXTURE_ID = 'env_0001';

function buildDeterministicTruth(envelopeId: string): TrustEnvelopeDeterministicTruthData {
  const verifiedRevenueMinor = 48_231_684n;
  const claimedRevenueMinor = 50_190_420n;
  const differenceMinor = verifiedRevenueMinor - claimedRevenueMinor;
  const suffix = envelopeId.slice(-1);

  if (suffix === '2') {
    return {
      verifiedRevenueMinor,
      claimedRevenueMinor,
      differenceMinor,
      differenceRateBps: -390,
      currencyCode: 'USD',
      matchVerdictStatus: 'matched_provisional',
      extractionFreshness: 'fresh',
      commerceEvidenceSource: 'Shopify settled orders + Stripe captured payments',
    };
  }

  if (suffix === '3') {
    return {
      verifiedRevenueMinor,
      claimedRevenueMinor,
      differenceMinor,
      differenceRateBps: -390,
      currencyCode: 'USD',
      matchVerdictStatus: 'unmatched',
      extractionFreshness: 'stale',
      commerceEvidenceSource: 'Shopify settled orders + Stripe captured payments',
    };
  }

  return {
    verifiedRevenueMinor,
    claimedRevenueMinor,
    differenceMinor,
    differenceRateBps: -390,
    currencyCode: 'USD',
    matchVerdictStatus: 'matched_confirmed',
    extractionFreshness: 'fresh',
    matchQuality: 'high',
    commerceEvidenceSource: 'Shopify settled orders + Stripe captured payments',
  };
}

function buildTrustEnvelopeSubject(_envelopeId: string): TrustEnvelopeSubjectData {
  return {
    subjectType: 'Revenue Claim Envelope',
    subjectIdentifier: 'subj_rc_2026_q2_meta_us_retargeting',
    relatedClaimId: 'claim_01JZ9Y4F2MM6D1R0QK8V',
    relatedClaimHref: '/app/claims/claim_0001',
    relatedChannelLabel: 'Meta Ads · Retargeting',
    relatedChannelHref: '/app/channels/ch_1',
    sourceSystem: 'Shopify · Stripe · Meta',
    timeWindowLabel: '2026-06-01 → 2026-06-30 (UTC)',
  };
}

function buildAttribution(_envelopeId: string): TrustEnvelopeAttributionData {
  return {
    selectedModel: 'Position-Based 40/20/40',
    modelFamily: 'Deterministic heuristic',
    modelAgreementTier: 'Moderate agreement',
    allocationChannel: 'Meta Ads',
    allocationPercent: 41.8,
    allocationAuthority: 'deterministic',
    boundaryNote: 'Attribution models are deterministic heuristics and do not prove causal lift.',
  };
}

function buildConfidence(envelopeId: string): TrustEnvelopeConfidenceData {
  const suffix = envelopeId.slice(-1);

  if (suffix === '2') {
    return {
      status: 'unavailable',
      authority: 'unavailable',
      boundaryNote: 'Confidence is advisory and cannot create financial truth.',
      reason: 'insufficient_data',
    };
  }

  if (suffix === '3') {
    return {
      status: 'delayed',
      authority: 'unavailable',
      boundaryNote: 'Confidence is advisory and cannot create financial truth.',
      reason: 'webhook_delay',
    };
  }

  return {
    status: 'available',
    intervalLower: 1.12,
    intervalUpper: 1.27,
    posteriorSupport: 0.91,
    modelFreshnessAt: '2026-07-02T13:06:00Z',
    authority: 'probabilistic',
    boundaryNote: 'Confidence is advisory and cannot create financial truth.',
  };
}

function buildBenchmark(_envelopeId: string): TrustEnvelopeBenchmarkData {
  return {
    status: 'available',
    rawBenchmark: '3.4x ROAS',
    decisionSafeBenchmark: '3.1x ROAS',
    benchmarkAuthority: 'benchmark',
    sourceClass: 'Peer cohort',
    coverageClass: 'US DTC Fashion • n=128',
    suppressionReason: null,
    comparableToPrevious: true,
    actionability: 'Advisory only',
  };
}

function buildPolicyAuthority(_envelopeId: string): TrustEnvelopePolicyAuthorityData {
  return {
    state: 'approval_required',
    explanation:
      'This envelope may be inspected and exported. Consequence-bearing actions require certification.',
    allowedActions: ['Inspect trust object', 'Export signed artifact', 'Open related claim'],
    blockedActions: ['Auto-execute budget changes', 'Submit spend changes'],
    auditRequirement: 'All consequence-bearing actions are written to the Audit Ledger.',
  };
}

function buildAuditReference(envelopeId: string): string {
  return envelopeId === PRIMARY_FIXTURE_ID ? 'AUD-2026-07-02-004182' : `AUD-2026-07-02-${envelopeId}`;
}

function buildTrustDetail(envelopeId: string, tenantId: string): TrustEnvelopeDetailDTO {
  const canonicalEnvelopeId =
    envelopeId === PRIMARY_FIXTURE_ID
      ? 'tenv_01JZA72J4M1WKH7RNPY5Q2A7S'
      : resolveTrustEnvelopeCanonicalId(envelopeId);

  return {
    envelopeId,
    canonicalEnvelopeId,
    tenantId,
    status: 'issued',
    createdAt: '2026-07-02T13:24:00Z',
    auditReference: buildAuditReference(envelopeId),
    subject: buildTrustEnvelopeSubject(envelopeId),
    deterministicTruth: buildDeterministicTruth(envelopeId),
    attribution: buildAttribution(envelopeId),
    confidence: buildConfidence(envelopeId),
    benchmark: buildBenchmark(envelopeId),
    policyAuthority: buildPolicyAuthority(envelopeId),
    versionStamp: `v_${envelopeId}_1`,
  };
}

export interface TrustEnvelopeDetailClient {
  getTrustEnvelopeDetail(
    tenantId: string,
    envelopeId: string,
    signal?: AbortSignal,
  ): Promise<TrustEnvelopeDetailOutcome>;
}

export function createTrustEnvelopeDetailClient(): TrustEnvelopeDetailClient {
  return {
    async getTrustEnvelopeDetail(tenantId, envelopeId, signal) {
      if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');
      resetDetailRequestCounter();
      incrementDetailRequest('trust-detail');

      if (!canViewTrustIndex(getCurrentUserRole())) {
        return { kind: 'permission_denied', message: DETAIL_COPY.permissionDenied };
      }
      if (!tenantId || !/^env_\d{4}$/.test(envelopeId)) {
        return { kind: 'not_found', message: DETAIL_COPY.notFound };
      }
      if (testMode === 'not_found') {
        return { kind: 'not_found', message: DETAIL_COPY.notFound };
      }

      const detail = buildTrustDetail(envelopeId, tenantId);
      const validation = validateTrustEnvelopeDetailDto(detail, envelopeId, tenantId);
      if (!validation.ok) {
        return { kind: validation.kind, message: DETAIL_COPY.schemaInvalid };
      }

      return { kind: 'loaded', detail };
    },
  };
}

let defaultClient: TrustEnvelopeDetailClient | null = null;

export function getDefaultTrustEnvelopeDetailClient(): TrustEnvelopeDetailClient {
  if (!defaultClient) defaultClient = createTrustEnvelopeDetailClient();
  return defaultClient;
}

export function resetDefaultTrustEnvelopeDetailClient(): void {
  defaultClient = null;
}
