import { getCurrentUserRole } from '../governance/governanceStore';
import { canViewClaims } from '../ledger/permissions';
import { baseClaimRow } from './claimsClient';
import { buildChannelCompositeId } from '../channels/channelIds';
import { DETAIL_COPY } from '../detail/copy';
import { buildVerifiedNarrative } from './claimDetailDisplay';
import type { ClaimEvidenceStep } from '../detail/types';
import {
  incrementDetailRequest,
  resetDetailRequestCounter,
} from '../detail/requestCounter';
import { validateClaimDetailDto } from '../detail/detailDtoValidation';
import type { ClaimDetailDTO, ClaimDetailOutcome } from '../detail/types';
import type { PolicyAuthorityState } from '../lib/types';

export type ClaimDetailTestMode =
  | 'default'
  | 'not_found'
  | 'permission_denied'
  | 'cross_tenant'
  | 'stale'
  | 'schema_invalid'
  | 'corrupted'
  | 'object_id_mismatch'
  | 'network_error';

let testMode: ClaimDetailTestMode = 'default';
let testDelayMs = 0;
let testDelayByClaimId: Record<string, number> = {};
let policyAuthorityOverride: PolicyAuthorityState | null = null;

export function setClaimDetailTestMode(mode: ClaimDetailTestMode): void {
  testMode = mode;
}

export function resetClaimDetailTestMode(): void {
  testMode = 'default';
  testDelayMs = 0;
  testDelayByClaimId = {};
  policyAuthorityOverride = null;
}

export function setClaimDetailPolicyAuthorityForTests(policy: PolicyAuthorityState | null): void {
  policyAuthorityOverride = policy;
}

export function setClaimDetailDelayForTests(ms: number): void {
  testDelayMs = ms;
}

export function setClaimDetailDelayByIdForTests(delays: Record<string, number>): void {
  testDelayByClaimId = delays;
}

export function resetClaimDetailDelayForTests(): void {
  testDelayMs = 0;
  testDelayByClaimId = {};
}

const ATTRIBUTION_MODELS = ['first-touch', 'last-touch', 'linear', 'time-decay'] as const;

const SECONDARY_PAID: Array<{ platform: string; campaignClass: string }> = [
  { platform: 'google_ads', campaignClass: 'paid_search' },
  { platform: 'linkedin_ads', campaignClass: 'paid_social' },
  { platform: 'tiktok_ads', campaignClass: 'paid_social' },
  { platform: 'meta_ads', campaignClass: 'paid_social' },
];

function campaignClassForClaimSource(claimSource: string): string {
  if (claimSource === 'google_ads') return 'paid_search';
  return 'paid_social';
}

function buildAttributionBreakdown(
  verifiedMinor: bigint,
  claimSource: string,
  discrepancyClass: string,
  index: number,
) {
  const primaryClass = campaignClassForClaimSource(claimSource);
  const primaryChannelId = buildChannelCompositeId(primaryClass, claimSource);

  if (discrepancyClass === 'within_tolerance') {
    return {
      paidAttribution: [
        {
          platform: claimSource,
          campaignClass: primaryClass,
          amountMinor: verifiedMinor,
          channelId: primaryChannelId,
        },
      ],
      journeyOrigins: [] as Array<{ commerceRail: string; amountMinor: bigint }>,
    };
  }

  const paidTotal = (verifiedMinor * 76n) / 100n;
  const journeyTotal = verifiedMinor - paidTotal;
  const primaryPaid = (paidTotal * 80n) / 100n;
  const secondaryPaid = paidTotal - primaryPaid;
  const secondary =
    SECONDARY_PAID.find((row) => row.platform !== claimSource) ?? SECONDARY_PAID[0]!;

  const paidAttribution = [
    {
      platform: claimSource,
      campaignClass: primaryClass,
      amountMinor: primaryPaid < 0n ? 0n : primaryPaid,
      channelId: primaryChannelId,
    },
    {
      platform: secondary.platform,
      campaignClass: secondary.campaignClass,
      amountMinor: secondaryPaid < 0n ? 0n : secondaryPaid,
      channelId: buildChannelCompositeId(secondary.campaignClass, secondary.platform),
    },
  ].filter((row) => row.amountMinor > 0n);

  const railOrder = ['direct', 'email', 'organic_search'] as const;
  const railWeights = [62n, 28n, 10n] as const;
  const rotated = [
    railOrder[index % 3]!,
    railOrder[(index + 1) % 3]!,
    railOrder[(index + 2) % 3]!,
  ];
  let allocated = 0n;
  const journeyOrigins = rotated.map((commerceRail, i) => {
    const amount =
      i === rotated.length - 1
        ? journeyTotal - allocated
        : (journeyTotal * railWeights[i]!) / 100n;
    allocated += amount;
    return { commerceRail, amountMinor: amount < 0n ? 0n : amount };
  }).filter((row) => row.amountMinor > 0n);

  return { paidAttribution, journeyOrigins };
}

function buildClaimEvents(
  claimRef: string,
  claimedMinor: bigint,
  index: number,
  unverified: boolean,
) {
  const baseDay = new Date('2026-10-12T14:00:00Z');
  baseDay.setUTCDate(baseDay.getUTCDate() + (index % 5));
  const firstAmount = claimedMinor / 2n;
  const secondAmount = claimedMinor - firstAmount;
  const dayLabel = (d: Date) =>
    d.toLocaleString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' });
  return [
    {
      id: `${claimRef}_evt_1`,
      // Platform is already named in the claim header — avoid "LinkedIn Ads Ad set".
      label: `Ad set ${100 + (index % 50)}, ${dayLabel(baseDay)}`,
      occurredAt: baseDay.toISOString(),
      claimedMinor: firstAmount,
      matchStatus: unverified ? ('unmatched' as const) : ('matched' as const),
    },
    {
      id: `${claimRef}_evt_2`,
      label: `Ad set ${200 + (index % 50)}, ${dayLabel(new Date(baseDay.getTime() + 86_400_000))}`,
      occurredAt: new Date(baseDay.getTime() + 86_400_000).toISOString(),
      claimedMinor: secondAmount,
      matchStatus:
        unverified || index % 5 === 0 ? ('unmatched' as const) : ('matched' as const),
    },
  ];
}

function buildEvidenceSteps(
  claimSource: string,
  commerceSource: string,
  claimRef: string,
  discrepancyClass: string,
): ClaimEvidenceStep[] {
  const platform = claimSource.replace(/_/g, ' ');
  const commerce = commerceSource === 'shopify' ? 'Shopify' : 'Stripe';
  return [
    {
      plainLabel: `Claim received from ${platform}`,
      timestamp: '2026-06-01T10:00:00Z',
      evidenceRef: `evt_${claimRef}_webhook`,
      phase: 'intake',
    },
    {
      plainLabel: 'Platform security seal verified',
      timestamp: '2026-06-01T10:00:12Z',
      evidenceRef: `sig_${claimRef}`,
      phase: 'intake',
      badge: 'Authentic',
    },
    {
      plainLabel: 'Customer privacy protected (PII removed)',
      timestamp: '2026-06-01T10:00:28Z',
      evidenceRef: `pii_${claimRef}`,
      phase: 'intake',
    },
    {
      plainLabel: `${commerce} payment confirmed`,
      timestamp: '2026-06-01T10:01:05Z',
      evidenceRef: `commerce_${claimRef}`,
      phase: 'verification',
      href: '/app/integrations',
      hrefLabel: 'View commerce integration',
    },
    {
      plainLabel: 'Reconciliation process started',
      timestamp: '2026-06-01T10:02:30Z',
      evidenceRef: `dispatch_${claimRef}`,
      phase: 'verification',
    },
    {
      plainLabel: 'Claim compared against payment',
      timestamp: '2026-06-01T10:03:45Z',
      evidenceRef: `verdict_${claimRef}`,
      phase: 'verification',
      badge: discrepancyClass === 'within_tolerance' ? 'Within tolerance' : '>10%',
    },
    {
      plainLabel: 'Official trust record generated',
      timestamp: '2026-06-01T10:04:10Z',
      evidenceRef: `envelope_${claimRef}`,
      phase: 'record',
      badge: 'Deterministic',
    },
    {
      plainLabel: 'Forensic audit trail secured',
      timestamp: '2026-06-01T10:04:22Z',
      evidenceRef: `audit_${claimRef}`,
      phase: 'record',
      href: '/app/audit',
      hrefLabel: 'Open audit ledger',
    },
  ];
}

function buildClaimDetail(claimId: string, tenantId: string): ClaimDetailDTO {
  const index = Math.max(0, parseInt(claimId.replace(/\D/g, ''), 10) - 1);
  const row = baseClaimRow(Number.isFinite(index) ? index : 0);
  const attributionModel = row.attributionModel;
  const agreementTier =
    index % 7 === 0 ? 'low_agreement' : index % 3 === 0 ? 'moderate_agreement' : 'high_agreement';
  const benchmarkAvailable = index % 4 !== 0;
  const sourceTransition = index % 6 === 0 && benchmarkAvailable;
  const unverified = index % 11 === 10;
  const verificationStatus = unverified ? 'unverified' : row.verificationStatus;
  const verifiedRevenueMinor = unverified ? 0n : row.verifiedRevenueMinor;
  const discrepancyAmountMinor = unverified
    ? row.claimedRevenueMinor
    : row.discrepancyAmountMinor;
  const discrepancyRateBps = unverified ? 10000 : row.discrepancyRateBps;
  const discrepancyClass = unverified ? 'material' : row.discrepancyClass;

  return {
    claimId: row.claimRef,
    tenantId,
    claimSource: row.claimSource,
    claimRef: row.claimRef,
    verificationStatus,
    claimedRevenueMinor: row.claimedRevenueMinor,
    verifiedRevenueMinor,
    currencyCode: row.currencyCode,
    discrepancyAmountMinor,
    discrepancyRateBps,
    discrepancyClass,
    commerceEvidenceSource: row.commerceSource,
    defaultAttributionModel: attributionModel,
    ...(unverified
      ? { paidAttribution: [], journeyOrigins: [] }
      : buildAttributionBreakdown(
          verifiedRevenueMinor,
          row.claimSource,
          discrepancyClass,
          index,
        )),
    claimEvents: buildClaimEvents(
      row.claimRef,
      row.claimedRevenueMinor,
      index,
      unverified,
    ),
    unverifiedReason: unverified
      ? 'Unverified Claim: No matching commerce receipt found.'
      : undefined,
    policyAuthority: policyAuthorityOverride ?? row.policyAuthority,
    confidence: row.confidence,
    benchmark: benchmarkAvailable
      ? {
          status: 'available',
          rawBenchmark: '14.2%',
          decisionSafeBenchmark: '12.0%',
          evidenceClass: sourceTransition ? 'tenant_longitudinal' : 'live_empirical',
          coverageClass: sourceTransition ? 'rolled_up' : 'exact',
          comparability: sourceTransition ? 'source_changed' : 'comparable',
          sourceTransition,
          transitionReason: sourceTransition ? 'Insufficient live cohort coverage' : undefined,
        }
      : {
          status: 'unavailable',
          reason: 'No benchmark coverage for this claim segment.',
        },
    attribution: {
      selectedModel: attributionModel,
      agreementTier,
      modelAssumption: 'Non-causal heuristic',
      causalStatus: 'correlational_only',
      negativeBoundaryCopy: DETAIL_COPY.modelComparisonBoundary,
      availableModels: [...ATTRIBUTION_MODELS],
    },
    audit: {
      auditReference: row.auditReference,
      accessEvents: [
        { timestamp: '2026-06-01T10:01:00Z', actor: 'tenant_operator', action: 'read_claim_detail' },
      ],
    },
    incrementalityBoundaryCopy: DETAIL_COPY.incrementalityBoundary,
    summaryCopy: 'Deterministic commerce evidence supports this platform claim under the selected attribution model.',
    verifiedNarrative: buildVerifiedNarrative(
      row.commerceSource,
      attributionModel,
      `${1000 + index}`,
    ),
    evidenceSteps: buildEvidenceSteps(
      row.claimSource,
      row.commerceSource,
      row.claimRef,
      discrepancyClass,
    ),
    technicalIdentifiers: {
      envelopeId: `env_${(row.claimRef.split('_').pop() ?? row.claimRef).padStart(4, '0')}`,
      tenantIdHash: `tenant_hash_${tenantId.slice(-6)}`,
    },
    auditSecuredAt: row.lastUpdated,
    versionStamp: `v_${row.claimRef}_1`,
  };
}

export interface ClaimDetailClient {
  getClaimDetail(
    tenantId: string,
    claimId: string,
    signal?: AbortSignal,
  ): Promise<ClaimDetailOutcome>;
}

export function createClaimDetailClient(): ClaimDetailClient {
  return {
    async getClaimDetail(tenantId, claimId, signal) {
      const delayMs = testDelayByClaimId[claimId] ?? testDelayMs;
      if (delayMs > 0) {
        await new Promise<void>((resolve, reject) => {
          const timer = setTimeout(resolve, delayMs);
          signal?.addEventListener('abort', () => {
            clearTimeout(timer);
            reject(new DOMException('Aborted', 'AbortError'));
          });
        });
      }
      if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');

      resetDetailRequestCounter();
      incrementDetailRequest('claim-detail');

      if (!canViewClaims(getCurrentUserRole())) {
        return { kind: 'permission_denied', message: DETAIL_COPY.permissionDenied };
      }
      if (!tenantId) {
        return { kind: 'schema_invalid', message: DETAIL_COPY.schemaInvalid };
      }
      if (testMode === 'not_found' || !/^claim_\d{4}$/.test(claimId)) {
        return { kind: 'not_found', message: DETAIL_COPY.notFound };
      }
      if (testMode === 'permission_denied') {
        return { kind: 'permission_denied', message: DETAIL_COPY.permissionDenied };
      }
      if (testMode === 'corrupted') {
        return { kind: 'corrupted_evidence', message: DETAIL_COPY.corruptedEvidence };
      }
      if (testMode === 'stale') {
        return { kind: 'stale_version', message: DETAIL_COPY.staleVersion };
      }
      if (testMode === 'network_error') {
        return { kind: 'network_error', message: DETAIL_COPY.networkError };
      }

      const detail = buildClaimDetail(claimId, testMode === 'cross_tenant' ? 'tenant_other' : tenantId);
      if (testMode === 'object_id_mismatch') {
        detail.claimId = 'claim_9999';
        detail.claimRef = 'claim_9999';
      }
      if (testMode === 'schema_invalid') {
        return { kind: 'schema_invalid', message: DETAIL_COPY.schemaInvalid };
      }

      const validation = validateClaimDetailDto(detail, claimId, tenantId);
      if (!validation.ok) {
        return {
          kind: validation.kind,
          message:
            validation.kind === 'object_id_mismatch'
              ? DETAIL_COPY.objectIdMismatch
              : DETAIL_COPY.scopeDenied,
        };
      }

      return { kind: 'loaded', detail };
    },
  };
}

let defaultClient: ClaimDetailClient | null = null;

export function getDefaultClaimDetailClient(): ClaimDetailClient {
  if (!defaultClient) defaultClient = createClaimDetailClient();
  return defaultClient;
}

export function resetDefaultClaimDetailClient(): void {
  defaultClient = null;
}
