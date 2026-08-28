import { getCurrentUserRole } from '../governance/governanceStore';
import { canViewChannels } from '../ledger/permissions';
import { DETAIL_COPY } from '../detail/copy';
import { incrementDetailRequest, resetDetailRequestCounter } from '../detail/requestCounter';
import { validateChannelDetailDto } from '../detail/detailDtoValidation';
import type { ChannelDetailDTO, ChannelDetailOutcome } from '../detail/types';
import { isValidChannelCompositeId } from './channelIds';

export function createChannelDetailClient(): {
  getChannelDetail(tenantId: string, channelId: string, signal?: AbortSignal): Promise<ChannelDetailOutcome>;
} {
  return {
    async getChannelDetail(tenantId, channelId, signal) {
      if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');
      resetDetailRequestCounter();
      incrementDetailRequest('channel-detail');

      if (!canViewChannels(getCurrentUserRole())) {
        return { kind: 'permission_denied', message: DETAIL_COPY.permissionDenied };
      }
      if (!tenantId || !isValidChannelCompositeId(channelId)) {
        return { kind: 'not_found', message: DETAIL_COPY.notFound };
      }

      const detail: ChannelDetailDTO = {
        channelId,
        tenantId,
        channelName: `Channel ${channelId}`,
        authorityStatus: 'deterministic_verified',
        verifiedRevenueOverTime: [
          { period: '2026-05', verifiedRevenueMinor: 450000n },
          { period: '2026-06', verifiedRevenueMinor: 512000n },
        ],
        reconciliation: {
          claimedRevenueMinor: 530000n,
          verifiedRevenueMinor: 512000n,
          currencyCode: 'USD',
          discrepancyClass: 'within_tolerance',
        },
        modelComparison: [
          {
            model: 'first_touch',
            verifiedRevenueAllocatedMinor: 180000n,
            shareOfVerifiedRevenueBps: 3515,
            modelAssumption: 'Credit first observed touch',
            agreementTier: 'low_agreement',
          },
          {
            model: 'last_touch',
            verifiedRevenueAllocatedMinor: 220000n,
            shareOfVerifiedRevenueBps: 4297,
            modelAssumption: 'Credit last observed touch',
            agreementTier: 'moderate_agreement',
          },
          {
            model: 'linear',
            verifiedRevenueAllocatedMinor: 200000n,
            shareOfVerifiedRevenueBps: 3906,
            modelAssumption: 'Equal credit across touches',
            agreementTier: 'moderate_agreement',
          },
        ],
        modelComparisonCopy: DETAIL_COPY.modelComparisonBoundary,
        confidence: {
          status: 'available',
          intervalLower: 0.78,
          intervalUpper: 0.9,
          methodOrContext: 'Artifact-backed',
        },
        benchmark: {
          status: 'available',
          rawBenchmark: '11.5%',
          decisionSafeBenchmark: '10.2%',
          evidenceClass: 'tenant_longitudinal',
          coverageClass: 'rolled_up',
          comparability: 'source_changed',
          sourceTransition: true,
          transitionReason: 'exact_bucket_now_available',
        },
        relatedClaims: [
          { claimRef: 'claim_0001', verificationStatus: 'verified' },
          { claimRef: 'claim_0002', verificationStatus: 'partial' },
        ],
        relatedEnvelopes: [{ envelopeId: 'env_0001', status: 'active' }],
        policyAuthority: 'blocked',
        auditReference: `aud_${channelId}`,
        versionStamp: `v_${channelId}_1`,
      };

      const validation = validateChannelDetailDto(detail, channelId, tenantId);
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

let defaultClient: ReturnType<typeof createChannelDetailClient> | null = null;

export function getDefaultChannelDetailClient() {
  if (!defaultClient) defaultClient = createChannelDetailClient();
  return defaultClient;
}

export function resetDefaultChannelDetailClient(): void {
  defaultClient = null;
}
