import { getCurrentUserRole } from '../governance/governanceStore';
import { canViewClaims } from '../ledger/permissions';
import { incrementLedgerRequest, resetLedgerRequestCounter } from '../ledger/requestCounter';
import { executeServerQuery, createSyntheticDataset } from '../ledger/queryEngine';
import { validateListDtoBoundary, FORBIDDEN_LIST_CLAIM_FIELDS } from '../ledger/listDtoValidation';
import { LEDGER_COPY } from '../ledger/copy';
import type { ClaimLedgerRowDTO, ConfidenceShape, LedgerListOutcome } from '../ledger/types';
import { buildDailyVerifiedRevenueMinor } from '../commandCenter/trendSyntheticData';
import { normalizeClaimsPageSize } from './claimsPagination';

export interface ClaimsFilters {
  dateFrom?: string;
  dateTo?: string;
  windowStart?: string;
  windowEnd?: string;
  trendDrill?: boolean;
  trendWindowLabel?: string;
  claimSource?: string;
  campaignClass?: string;
  commerceRail?: string;
  commerceSource?: string;
  verificationStatus?: string;
  discrepancyClass?: string;
  policyAuthority?: string;
  search?: string;
  sortKey?: string;
  sortDirection?: 'asc' | 'desc';
  offset?: number;
  pageSize?: number;
}

export interface ClaimsLedgerClient {
  listClaims(tenantId: string, filters: ClaimsFilters, signal?: AbortSignal): Promise<LedgerListOutcome<ClaimLedgerRowDTO>>;
}

let testListClaimsDelayMs = 0;
let testListClaimsDelayForOffset: number | null = null;
let testListClaimsDelayBySource: Record<string, number> = {};

export function setClaimsListDelayForTests(ms: number, onlyForOffset?: number): void {
  testListClaimsDelayMs = ms;
  testListClaimsDelayForOffset = onlyForOffset ?? null;
}

export function setClaimsListDelayBySourceForTests(delays: Record<string, number>): void {
  testListClaimsDelayBySource = delays;
}

export function resetClaimsListDelayForTests(): void {
  testListClaimsDelayMs = 0;
  testListClaimsDelayForOffset = null;
  testListClaimsDelayBySource = {};
}

async function maybeDelayForTests(filters: ClaimsFilters, signal?: AbortSignal): Promise<void> {
  const sourceDelay = filters.claimSource ? testListClaimsDelayBySource[filters.claimSource] : undefined;
  const ms =
    sourceDelay ??
    (testListClaimsDelayMs > 0 &&
    (testListClaimsDelayForOffset === null || (filters.offset ?? 0) === testListClaimsDelayForOffset)
      ? testListClaimsDelayMs
      : 0);
  if (!ms) return;
  await new Promise<void>((resolve, reject) => {
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener('abort', () => {
      clearTimeout(timer);
      reject(new DOMException('Aborted', 'AbortError'));
    });
  });
}

const CLAIMS_PER_TREND_DAY = 4;
const TREND_WINDOW_DAYS = 61;
const DAILY_CLAIM_SHARES = [24n, 26n, 23n, 27n] as const;

const CAMPAIGN_CLASSES = ['paid_search', 'paid_social', 'creator', 'branded', 'affiliate'] as const;
const COMMERCE_RAILS = ['organic', 'direct', 'referral', 'email'] as const;
const CLAIM_PLATFORMS = ['meta_ads', 'google_ads', 'tiktok_ads', 'linkedin_ads'] as const;
const ATTRIBUTION_MODELS = ['last-touch', 'linear', 'time-decay', 'first-touch'] as const;
const POLICY_ROTATION: Array<import('../lib/types').PolicyAuthorityState> = [
  'blocked',
  'simulation_only',
  'proposal_required',
  'approval_required',
];

function buildClaimConfidence(index: number, isVerifiedExportGoldenPath: boolean): ConfidenceShape {
  if (isVerifiedExportGoldenPath) {
    return {
      status: 'available',
      intervalLower: 0.88,
      intervalUpper: 0.96,
      methodOrContext: 'Bounded Bayesian fit (tenant-scoped)',
      qualitativeState: 'Exact bucket',
    };
  }

  const mod = index % 30;
  if (mod === 0) {
    return { status: 'unavailable', reason: 'cold_start_insufficient_data' };
  }
  if (mod === 5) {
    return { status: 'unavailable', reason: 'insufficient_data' };
  }
  if (mod === 7) {
    return {
      status: 'available',
      intervalLower: 0.55,
      intervalUpper: 0.68,
      methodOrContext: 'Bounded Bayesian fit',
      qualitativeState: 'Wide posterior — model disagreement',
    };
  }
  if (mod === 10) {
    return { status: 'unavailable', reason: 'worker_failure' };
  }
  if (mod === 13) {
    return {
      status: 'available',
      intervalLower: 0.88,
      intervalUpper: 0.96,
      methodOrContext: 'Bounded Bayesian fit',
      qualitativeState: 'Exact bucket',
    };
  }
  if (mod === 15) {
    return { status: 'unavailable', reason: 'refit_locked' };
  }
  if (mod === 20) {
    return { status: 'delayed', reason: 'bayesian_timeout' };
  }

  return {
    status: 'available',
    intervalLower: 0.82,
    intervalUpper: 0.94,
    methodOrContext: 'Bayesian posterior (tenant-scoped)',
    qualitativeState: 'Stable posterior',
  };
}

export function baseClaimRow(index: number): ClaimLedgerRowDTO {
  const daysAgo = Math.floor(index / CLAIMS_PER_TREND_DAY);
  const slot = index % CLAIMS_PER_TREND_DAY;
  const dayIndex = TREND_WINDOW_DAYS - 1 - daysAgo;
  const dayTotal = buildDailyVerifiedRevenueMinor(dayIndex);
  const verified = (dayTotal * DAILY_CLAIM_SHARES[slot]!) / 100n;
  const claimed = verified + BigInt(index % 3 === 0 ? 25_000 : 0);
  const day = new Date();
  day.setUTCHours(9 + slot * 3, 0, 0, 0);
  day.setUTCDate(day.getUTCDate() - daysAgo);
  const isVerifiedExportGoldenPath = index === 0;
  const discrepancyClass = isVerifiedExportGoldenPath
    ? 'within_tolerance'
    : index % 3 === 0
      ? 'flagged'
      : 'within_tolerance';
  const matchVerdict = isVerifiedExportGoldenPath
    ? 'within_tolerance'
    : index % 5 === 0
      ? 'verified'
      : index % 4 === 0
        ? 'rejected'
        : discrepancyClass === 'flagged'
          ? 'flagged'
          : 'within_tolerance';

  return {
    claimRef: `claim_${String(index + 1).padStart(4, '0')}`,
    claimTime: day.toISOString(),
    claimSource: CLAIM_PLATFORMS[index % CLAIM_PLATFORMS.length]!,
    campaignClass: CAMPAIGN_CLASSES[index % CAMPAIGN_CLASSES.length]!,
    commerceRail: COMMERCE_RAILS[index % COMMERCE_RAILS.length]!,
    commerceSource: index % 3 === 0 ? 'shopify' : 'stripe',
    claimedRevenueMinor: claimed,
    verifiedRevenueMinor: verified,
    currencyCode: 'USD',
    discrepancyAmountMinor: claimed - verified,
    discrepancyRateBps: Number(((claimed - verified) * 10000n) / (claimed || 1n)),
    discrepancyClass,
    matchVerdict,
    attributionModel: ATTRIBUTION_MODELS[index % ATTRIBUTION_MODELS.length]!,
    verificationStatus:
      isVerifiedExportGoldenPath ? 'verified' : index % 4 === 0 ? 'partial' : 'verified',
    confidence: buildClaimConfidence(index, isVerifiedExportGoldenPath),
    policyAuthority: POLICY_ROTATION[index % POLICY_ROTATION.length]!,
    auditReference: `aud_claim_${index}`,
    lastUpdated: day.toISOString(),
    futureDetailAffordance: 'detail_blocked_level_8',
  };
}

let syntheticClaims = createSyntheticDataset(baseClaimRow, 244);

export function setSyntheticClaimsDataset(count: number): void {
  syntheticClaims = createSyntheticDataset(baseClaimRow, count);
}

export function resetSyntheticClaimsDataset(): void {
  syntheticClaims = createSyntheticDataset(baseClaimRow, 244);
}

export function createClaimsLedgerClient(dataset = syntheticClaims): ClaimsLedgerClient {
  return {
    async listClaims(tenantId, filters, signal) {
      await maybeDelayForTests(filters, signal);
      if (signal?.aborted) {
        throw new DOMException('Aborted', 'AbortError');
      }
      resetLedgerRequestCounter();
      incrementLedgerRequest('claims');

      const role = getCurrentUserRole();
      if (!canViewClaims(role)) {
        return { kind: 'permission_denied', message: LEDGER_COPY.permissionDenied };
      }

      if (!tenantId) {
        return { kind: 'unknown_error', message: 'Tenant required' };
      }

      const result = executeServerQuery<ClaimLedgerRowDTO>('claims', {
        items: dataset,
        params: {
          ...filters,
          filters: {
            claimSource: filters.claimSource,
            campaignClass: filters.campaignClass,
            commerceRail: filters.commerceRail,
            commerceSource: filters.commerceSource,
            verificationStatus: filters.verificationStatus,
            discrepancyClass: filters.discrepancyClass,
            policyAuthority: filters.policyAuthority,
            dateFrom: filters.dateFrom,
            dateTo: filters.dateTo,
            windowStart: filters.windowStart,
            windowEnd: filters.windowEnd,
          },
          search: filters.search,
          sortKey: filters.sortKey ?? 'lastUpdated',
          sortDirection: filters.sortDirection ?? 'desc',
          offset: filters.offset,
          pageSize: normalizeClaimsPageSize(filters.pageSize),
        },
        defaultSortKey: 'lastUpdated',
        filterFn: (row, f, search) => {
          if (f.claimSource && row.claimSource !== f.claimSource) return false;
          if (f.campaignClass && row.campaignClass !== f.campaignClass) return false;
          if (f.commerceRail && row.commerceRail !== f.commerceRail) return false;
          if (f.commerceSource && row.commerceSource !== f.commerceSource) return false;
          if (f.verificationStatus && row.verificationStatus !== f.verificationStatus) return false;
          if (f.discrepancyClass && row.discrepancyClass !== f.discrepancyClass) return false;
          if (f.policyAuthority && row.policyAuthority !== f.policyAuthority) return false;
          if (f.dateFrom && row.lastUpdated.slice(0, 10) < f.dateFrom) return false;
          if (f.dateTo && row.lastUpdated.slice(0, 10) > f.dateTo) return false;
          if (f.windowStart && row.lastUpdated < f.windowStart) return false;
          if (f.windowEnd && row.lastUpdated >= f.windowEnd) return false;
          if (search && !row.claimRef.toLowerCase().includes(search.toLowerCase())) return false;
          return true;
        },
        getSortValue: (row, key) => {
          if (key === 'claimSource') return row.claimSource;
          if (key === 'campaignClass') return row.campaignClass;
          if (key === 'commerceRail') return row.commerceRail;
          if (key === 'discrepancy') return Number(row.discrepancyAmountMinor);
          if (key === 'verificationStatus') return row.verificationStatus;
          if (key === 'date' || key === 'lastUpdated') return row.lastUpdated;
          return row.claimRef;
        },
      });

      if ('error' in result) {
        return { kind: result.error, message: result.message } as const;
      }

      for (const row of result.rows) {
        const boundary = validateListDtoBoundary(row, FORBIDDEN_LIST_CLAIM_FIELDS);
        if (!boundary.ok) {
          return {
            kind: 'schema_invalid',
            message: `Forbidden list fields: ${boundary.fields.join(', ')}`,
          };
        }
      }

      if (result.metadata.totalCount === 0) {
        const hasFilters = Object.values(filters).some(
          (v) => v !== undefined && v !== '' && !['offset', 'pageSize', 'sortKey', 'sortDirection'].includes(String(v)),
        );
        if (hasFilters) {
          return { kind: 'filtered_empty', rows: [], ...result.metadata };
        }
        return { kind: 'empty', rows: [], ...result.metadata };
      }

      return { kind: 'loaded', rows: result.rows, ...result.metadata };
    },
  };
}

let defaultClient: ClaimsLedgerClient | null = null;

export function getDefaultClaimsLedgerClient(): ClaimsLedgerClient {
  if (!defaultClient) defaultClient = createClaimsLedgerClient();
  return defaultClient;
}

export function setDefaultClaimsLedgerClient(client: ClaimsLedgerClient): void {
  defaultClient = client;
}

export function resetDefaultClaimsLedgerClient(): void {
  defaultClient = null;
}
