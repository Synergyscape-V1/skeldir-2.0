import { getCurrentUserRole } from '../governance/governanceStore';

import { canViewTrustIndex } from '../ledger/permissions';

import { incrementLedgerRequest, resetLedgerRequestCounter } from '../ledger/requestCounter';

import { executeServerQuery, createSyntheticDataset } from '../ledger/queryEngine';

import {

  validateListDtoBoundary,

  FORBIDDEN_LIST_ENVELOPE_FIELDS,

  measureListPayloadBytes,

  MAX_LIST_ROW_PAYLOAD_BYTES,

} from '../ledger/listDtoValidation';

import { LEDGER_COPY } from '../ledger/copy';

import type {

  LedgerListOutcome,

  TrustEnvelopeIndexRowDTO,

  TrustEnvelopeIndexSummary,

  TrustEnvelopeMatchVerdict,

  AuditRecordStatus,

  DiscrepancyClass,

  BenchmarkEvidenceClass,

} from '../ledger/types';

import type { PolicyAuthorityState } from '../lib/types';

import {

  buildTrustIndexFilterRecord,

  matchesTrustIndexRow,

} from './trustIndexFilterMatching';

import { computeTrustIndexSummary, emptyTrustIndexSummary } from './trustIndexSummary';
import { TRUST_INDEX_DEFAULT_PAGE_SIZE } from './trustIndexQueryState';
import {
  TRUST_INDEX_DEFAULT_SORT_KEY,
  trustEnvelopeSortComparator,
} from './trustIndexEnvelopeDisplay';
import {
  buildSyntheticTrustEnvelopeAuditEventId,
  buildSyntheticTrustEnvelopeId,
  DEFAULT_SYNTHETIC_TRUST_ENVELOPE_COUNT,
} from './trustEnvelopeAuditIdentity';



export interface TrustIndexFilters {

  verificationStatus?: 'verified' | 'partial' | 'unverified' | 'disputed';

  discrepancyClass?: DiscrepancyClass;

  policyAuthority?: PolicyAuthorityState;

  confidenceAvailability?: 'available' | 'unavailable';

  benchmarkSource?: BenchmarkEvidenceClass;

  sortKey?: string;

  sortDirection?: 'asc' | 'desc';

  offset?: number;

  pageSize?: number;

  status?: string;

}



export type TrustIndexListOutcome = LedgerListOutcome<TrustEnvelopeIndexRowDTO> & {

  summary?: TrustEnvelopeIndexSummary;

};



export interface TrustIndexClient {

  listEnvelopes(

    tenantId: string,

    filters: TrustIndexFilters,

    signal?: AbortSignal,

  ): Promise<TrustIndexListOutcome>;

}



const POLICY_CYCLE: PolicyAuthorityState[] = [

  'blocked',

  'approval_required',

  'proposal_required',

  'blocked',

  'approval_required',

  'blocked',

];



const CHANNEL_SOURCES = ['stripe', 'meta_ads', 'google_ads', 'shopify'] as const;

function buildDiscrepancyFixture(index: number): { bps: number; discrepancyClass: DiscrepancyClass } {
  const mod = index % 6;
  if (mod === 0) return { bps: 50, discrepancyClass: 'within_tolerance' };
  if (mod === 1) return { bps: 500, discrepancyClass: 'flagged' };
  if (mod === 2) return { bps: 1500, discrepancyClass: 'material' };
  if (mod === 3) return { bps: 0, discrepancyClass: 'within_tolerance' };
  if (mod === 4) return { bps: 800, discrepancyClass: 'flagged' };
  return { bps: 2000, discrepancyClass: 'material' };
}

function buildMatchVerdict(index: number, discrepancyClass: DiscrepancyClass): TrustEnvelopeMatchVerdict {
  if (discrepancyClass === 'within_tolerance') {
    return index % 3 === 0 ? 'matched_provisional' : 'matched_confirmed';
  }
  if (discrepancyClass === 'flagged') {
    return index % 2 === 0 ? 'adjusted' : 'matched_provisional';
  }
  return index % 4 === 0 ? 'adjusted' : 'unmatched';
}

function deriveClaimedRevenue(verified: bigint, bps: number, index: number): bigint {
  const delta = (verified * BigInt(bps)) / 10000n;
  if (bps === 0) return verified;
  return index % 2 === 0 ? verified + delta : verified - delta;
}

const SUBJECT_FIXTURES = [
  { label: 'Revenue Claim', detail: 'Stripe payout / Checkout US-East' },
  { label: 'Channel settlement', detail: 'Meta Ads reconciliation' },
  { label: 'Revenue Claim', detail: 'Shopify order / EU storefront' },
  { label: 'Audit artifact', detail: 'Refund reversal clause' },
] as const;

const ATTRIBUTION_FIXTURES = [
  { model: 'Last-touch + holdout', authority: 'probabilistic' as const },
  { model: 'Bayesian blended', authority: 'probabilistic' as const },
  { model: 'Time-decay model', authority: 'deterministic' as const },
  { model: 'Rules-based allocation', authority: 'deterministic' as const },
] as const;

function buildBenchmark(index: number) {

  const mod = index % 5;

  if (mod === 0) {

    return {

      status: 'unavailable' as const,

      reason: 'Insufficient cross-tenant signal.',

      evidenceClass: 'unavailable' as const,

    };

  }

  if (mod === 1) {

    return {

      status: 'suppressed' as const,

      suppressionReason: 'Benchmark suppressed by privacy gate.',

      evidenceClass: 'unavailable' as const,

    };

  }

  const evidenceClass: BenchmarkEvidenceClass =
    mod === 2 ? 'live_empirical' : mod === 3 ? 'tenant_longitudinal' : 'historical_prior';

  return {

    status: 'available' as const,

    decisionSafeBenchmark: mod === 2 ? 'Segment P75' : mod === 3 ? 'Segment P50' : 'Governed prior',

    evidenceClass,

    coverageClass: 'decision_safe',

  };

}



function buildAuditRecordStatus(index: number): AuditRecordStatus {

  if (index % 35 === 0) return 'pending_review';

  if (index % 17 === 0) return 'unavailable';

  return 'linked';

}



function baseEnvelopeRow(index: number): TrustEnvelopeIndexRowDTO {

  const subject = SUBJECT_FIXTURES[index % SUBJECT_FIXTURES.length];

  const attribution = ATTRIBUTION_FIXTURES[index % ATTRIBUTION_FIXTURES.length];

  const verifiedRevenueMinor = BigInt(4_821_290 + index * 137_211);

  const { bps, discrepancyClass } = buildDiscrepancyFixture(index);

  const claimedRevenueMinor = deriveClaimedRevenue(verifiedRevenueMinor, bps, index);

  const discrepancyAmountMinor = claimedRevenueMinor - verifiedRevenueMinor;

  const claimTime = new Date(Date.now() - index * 7200_000).toISOString();

  const claimSource = CHANNEL_SOURCES[index % CHANNEL_SOURCES.length];

  return {

    envelopeId: buildSyntheticTrustEnvelopeId(index),

    subjectRef: `commerce_event_${index + 1}`,

    subjectLabel: subject.label,

    subjectDetail: subject.detail,

    claimTime,

    claimSource,

    claimedRevenueMinor,

    verifiedRevenueMinor,

    currencyCode: 'USD',

    discrepancyAmountMinor,

    discrepancyRateBps: bps,

    discrepancyClass,

    matchVerdict: buildMatchVerdict(index, discrepancyClass),

    verificationStatus: index % 4 === 0 ? 'partial' : index % 11 === 0 ? 'unverified' : 'verified',

    revenueAuthority: 'deterministic',

    attributionModel: attribution.model,

    attributionAuthority: attribution.authority,

    confidence:

      index % 4 === 0

        ? { status: 'unavailable', reason: 'cold_start_insufficient_data' }

        : index % 13 === 0

          ? { status: 'unavailable', reason: 'bayesian_timeout' }

          : {

              status: 'available',

              authority: 'probabilistic',

              intervalLower: 0.78,

              intervalUpper: 0.91,

              methodOrContext: 'Bounded Bayesian fit',

            },

    benchmark: buildBenchmark(index),

    auditRecordStatus: buildAuditRecordStatus(index),

    policyAuthority: POLICY_CYCLE[index % POLICY_CYCLE.length],

    channelSource: claimSource,

    auditReference: buildSyntheticTrustEnvelopeAuditEventId(index),

    generationTimestamp: claimTime,

    status: index % 7 === 0 ? 'superseded' : 'active',

    futureDetailAffordance: 'detail_blocked_level_8',

  };

}



let syntheticEnvelopes = createSyntheticDataset(
  baseEnvelopeRow,
  DEFAULT_SYNTHETIC_TRUST_ENVELOPE_COUNT,
);



export function setSyntheticTrustIndexDataset(count: number): void {

  syntheticEnvelopes = createSyntheticDataset(baseEnvelopeRow, count);

}



function filterDataset(dataset: TrustEnvelopeIndexRowDTO[], filters: TrustIndexFilters) {

  const filterRecord = buildTrustIndexFilterRecord(filters);

  return dataset.filter((row) => matchesTrustIndexRow(row, filterRecord));

}



export function createTrustIndexClient(dataset = syntheticEnvelopes): TrustIndexClient {

  return {

    async listEnvelopes(tenantId, filters) {

      resetLedgerRequestCounter();

      incrementLedgerRequest('trust-index');



      if (!canViewTrustIndex(getCurrentUserRole())) {

        return { kind: 'permission_denied', message: LEDGER_COPY.permissionDenied };

      }

      if (!tenantId) return { kind: 'unknown_error', message: 'Tenant required' };



      const filtered = filterDataset(dataset, filters);

      const summary = computeTrustIndexSummary(filtered);



      const result = executeServerQuery<TrustEnvelopeIndexRowDTO>('trust-index', {

        items: filtered,

        params: {

          sortKey: filters.sortKey ?? TRUST_INDEX_DEFAULT_SORT_KEY,

          sortDirection: filters.sortDirection ?? 'desc',

          offset: filters.offset,

          pageSize: filters.pageSize ?? TRUST_INDEX_DEFAULT_PAGE_SIZE,

        },

        defaultSortKey: TRUST_INDEX_DEFAULT_SORT_KEY,

        sortFn: trustEnvelopeSortComparator,

        getSortValue: (row, key) => {

          if (key === 'claimTime' || key === 'generationTimestamp' || key === 'date') return row.claimTime;

          if (key === 'discrepancyRateBps') return row.discrepancyRateBps;

          if (key === 'policyAuthority') return row.policyAuthority;

          return row.envelopeId;

        },

      });



      if ('error' in result) {

        return { kind: result.error, message: result.message, summary: emptyTrustIndexSummary() };

      }



      for (const row of result.rows) {

        const boundary = validateListDtoBoundary(row, FORBIDDEN_LIST_ENVELOPE_FIELDS);

        if (!boundary.ok) {

          return {

            kind: 'payload_oversized',

            message: `Forbidden fields: ${boundary.fields.join(', ')}`,

            summary: emptyTrustIndexSummary(),

          };

        }

        if (measureListPayloadBytes(row) > MAX_LIST_ROW_PAYLOAD_BYTES) {

          return {

            kind: 'payload_oversized',

            message: 'List row exceeds payload budget',

            summary: emptyTrustIndexSummary(),

          };

        }

      }



      const hasFilters = Boolean(

        filters.status ||

          filters.verificationStatus ||

          filters.discrepancyClass ||

          filters.policyAuthority ||

          filters.confidenceAvailability ||

          filters.benchmarkSource,

      );



      if (result.metadata.totalCount === 0) {

        if (hasFilters) {

          return { kind: 'filtered_empty', rows: [], summary, ...result.metadata };

        }

        return { kind: 'empty', rows: [], summary: emptyTrustIndexSummary(), ...result.metadata };

      }



      return { kind: 'loaded', rows: result.rows, summary, ...result.metadata };

    },

  };

}



let defaultClient: TrustIndexClient | null = null;



export function getDefaultTrustIndexClient(): TrustIndexClient {

  if (!defaultClient) defaultClient = createTrustIndexClient();

  return defaultClient;

}



export function resetDefaultTrustIndexClient(): void {

  defaultClient = null;

  syntheticEnvelopes = createSyntheticDataset(
    baseEnvelopeRow,
    DEFAULT_SYNTHETIC_TRUST_ENVELOPE_COUNT,
  );

}


