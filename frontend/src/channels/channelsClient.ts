import { getCurrentUserRole } from '../governance/governanceStore';
import { canViewChannels } from '../ledger/permissions';
import { incrementLedgerRequest, resetLedgerRequestCounter } from '../ledger/requestCounter';
import { executeServerQuery } from '../ledger/queryEngine';
import { LEDGER_COPY } from '../ledger/copy';
import type { ChannelOverviewRowDTO, ChannelOverviewSummary, LedgerListOutcome } from '../ledger/types';
import { CHANNELS_OVERVIEW_FIXTURES } from './channelsFixtures';
import { computeChannelOverviewSummary } from './channelsSummary';
import { CHANNELS_DEFAULT_PAGE_SIZE } from './channelsPagination';
import { channelRowIdentityLabel, channelsClaimSourceLabel } from './channelsDisplay';
import { parseModelAgreementPercentToBps } from '../trust/revenueReliability';

export type ChannelsMetricBasis = 'verified' | 'platform_claim';

export interface ChannelsFilters {
  dateFrom?: string;
  dateTo?: string;
  channelId?: string;
  attributionChannel?: string;
  claimSource?: string;
  commerceSource?: string;
  attributionAgreement?: 'under_90' | 'under_80' | 'all';
  bayesianStatus?: 'needs_review' | 'healthy' | 'unavailable' | 'degraded';
  benchmarkStatus?: 'attention_needed' | 'stable' | 'transitioning' | 'unavailable';
  actionAuthority?: string;
  metricBasis?: ChannelsMetricBasis;
  search?: string;
  sortKey?: string;
  sortDirection?: 'asc' | 'desc';
  offset?: number;
  pageSize?: number;
}

export type ChannelsListOutcome = LedgerListOutcome<ChannelOverviewRowDTO> & {
  summary?: ChannelOverviewSummary;
};

export interface ChannelsClient {
  listChannels(
    tenantId: string,
    filters: ChannelsFilters,
    signal?: AbortSignal,
  ): Promise<ChannelsListOutcome>;
}

const POLICY_SORT_RANK: Record<string, number> = {
  approval_required: 0,
  proposal_required: 1,
  auto_executable_within_policy: 2,
  simulation_only: 3,
  blocked: 4,
};

function matchesBayesianFilter(row: ChannelOverviewRowDTO, filter?: ChannelsFilters['bayesianStatus']): boolean {
  if (!filter) return true;
  if (filter === 'needs_review') {
    return row.bayesianStatusKey === 'degraded' || row.bayesianStatusKey === 'low_confidence' || row.bayesianStatusKey === 'unavailable';
  }
  if (filter === 'healthy') return row.bayesianStatusKey === 'healthy';
  if (filter === 'unavailable') return row.bayesianStatusKey === 'unavailable' || row.bayesianStatusKey === 'degraded';
  if (filter === 'degraded') return row.bayesianStatusKey === 'degraded';
  return true;
}

function matchesBenchmarkFilter(row: ChannelOverviewRowDTO, filter?: ChannelsFilters['benchmarkStatus']): boolean {
  if (!filter) return true;
  if (filter === 'attention_needed') {
    return row.benchmarkStatusKey === 'attention_needed' || row.benchmarkStatusKey === 'transitioning' || row.benchmark.status === 'unavailable';
  }
  if (filter === 'stable') return row.benchmarkStatusKey === 'stable';
  if (filter === 'transitioning') return row.benchmarkStatusKey === 'transitioning';
  if (filter === 'unavailable') return row.benchmarkStatusKey === 'unavailable' || row.benchmark.status === 'unavailable';
  return true;
}

function matchesActionAuthority(row: ChannelOverviewRowDTO, filter?: string): boolean {
  if (!filter) return true;
  if (filter === 'actionable_only') {
    return row.policyAuthority !== 'blocked';
  }
  return row.policyAuthority === filter;
}

function matchesAttributionAgreement(row: ChannelOverviewRowDTO, filter?: ChannelsFilters['attributionAgreement']): boolean {
  if (!filter || filter === 'all') return true;
  const bps = parseModelAgreementPercentToBps(row.attributionModelAgreement);
  if (filter === 'under_90') return bps < 9000;
  if (filter === 'under_80') return bps < 8000;
  return true;
}

function channelSortValue(row: ChannelOverviewRowDTO, key: string): string | number {
  switch (key) {
    case 'channelName':
      return row.channelName.toLowerCase();
    case 'attributionChannel':
      return row.attributionChannel.toLowerCase();
    case 'claimSource':
      return row.claimSource.toLowerCase();
    case 'verifiedRevenue':
      return Number(row.verifiedRevenueMinor);
    case 'claimedRevenue':
      return Number(row.claimedRevenueMinor);
    case 'discrepancyRateBps':
    case 'discrepancy':
      return row.discrepancyRateBps;
    case 'attributionAgreement':
      return parseModelAgreementPercentToBps(row.attributionModelAgreement);
    case 'bayesianStatus':
      return row.bayesianStatusKey;
    case 'benchmarkStatus':
      return row.benchmarkStatusKey;
    case 'policyAuthority':
      return POLICY_SORT_RANK[row.policyAuthority] ?? 99;
    default:
      return row.channelName.toLowerCase();
  }
}

function channelSortFn(
  a: ChannelOverviewRowDTO,
  b: ChannelOverviewRowDTO,
  key: string,
  direction: 'asc' | 'desc',
): number {
  const av = channelSortValue(a, key);
  const bv = channelSortValue(b, key);
  if (av < bv) return direction === 'asc' ? -1 : 1;
  if (av > bv) return direction === 'asc' ? 1 : -1;
  return a.channelId.localeCompare(b.channelId);
}

let syntheticChannels = [...CHANNELS_OVERVIEW_FIXTURES];

export function setSyntheticChannelsDataset(rows: ChannelOverviewRowDTO[]): void {
  syntheticChannels = rows;
}

export function resetSyntheticChannelsDataset(): void {
  syntheticChannels = [...CHANNELS_OVERVIEW_FIXTURES];
}

export function createChannelsClient(dataset = syntheticChannels): ChannelsClient {
  return {
    async listChannels(_tenantId, filters, signal) {
      if (signal?.aborted) {
        return { kind: 'network_error', message: 'Request aborted' };
      }
      resetLedgerRequestCounter();
      incrementLedgerRequest('channels');
      if (!canViewChannels(getCurrentUserRole())) {
        return { kind: 'permission_denied', message: LEDGER_COPY.permissionDenied };
      }

      const filterFn = (row: ChannelOverviewRowDTO, _f: Record<string, string | undefined>, search?: string) => {
        if (filters.channelId && row.channelId !== filters.channelId) return false;
        if (filters.attributionChannel && row.attributionChannel !== filters.attributionChannel) return false;
        if (filters.claimSource && row.claimSource !== filters.claimSource) return false;
        if (filters.commerceSource && row.commerceSource !== filters.commerceSource) return false;
        if (!matchesAttributionAgreement(row, filters.attributionAgreement)) return false;
        if (!matchesBayesianFilter(row, filters.bayesianStatus)) return false;
        if (!matchesBenchmarkFilter(row, filters.benchmarkStatus)) return false;
        if (!matchesActionAuthority(row, filters.actionAuthority)) return false;
        if (search) {
          const haystack = [
            row.channelName,
            row.attributionChannel,
            channelsClaimSourceLabel(row.claimSource),
            row.claimSource,
            channelRowIdentityLabel(row),
          ]
            .join(' ')
            .toLowerCase();
          if (!haystack.includes(search.toLowerCase())) return false;
        }
        return true;
      };

      const allMatching = dataset.filter((row) => filterFn(row, {}, filters.search));
      const summary = computeChannelOverviewSummary(allMatching);

      const result = executeServerQuery<ChannelOverviewRowDTO>('channels', {
        items: dataset,
        params: {
          ...filters,
          filters: {
            channelId: filters.channelId,
            claimSource: filters.claimSource,
            commerceSource: filters.commerceSource,
          },
          search: filters.search,
          sortKey: filters.sortKey ?? 'policyAuthority',
          sortDirection: filters.sortDirection ?? 'asc',
          offset: filters.offset,
          pageSize: filters.pageSize ?? CHANNELS_DEFAULT_PAGE_SIZE,
        },
        defaultSortKey: 'policyAuthority',
        filterFn,
        sortFn: channelSortFn,
        getSortValue: channelSortValue,
      });

      if ('error' in result) {
        return { kind: 'sort_invalid', message: result.message } as const;
      }

      if (result.metadata.totalCount === 0) {
        const hasFilters = Boolean(
          filters.search ||
          filters.channelId ||
          filters.attributionChannel ||
          filters.claimSource ||
          filters.commerceSource ||
          filters.attributionAgreement ||
          filters.bayesianStatus ||
          filters.benchmarkStatus ||
          filters.actionAuthority,
        );
        if (hasFilters) {
          return { kind: 'filtered_empty', rows: [], summary, ...result.metadata };
        }
        return { kind: 'empty', rows: [], summary, ...result.metadata };
      }

      return { kind: 'loaded', rows: result.rows, summary, ...result.metadata };
    },
  };
}

let defaultClient: ChannelsClient | null = null;
export function getDefaultChannelsClient(): ChannelsClient {
  if (!defaultClient) defaultClient = createChannelsClient();
  return defaultClient;
}
export function resetDefaultChannelsClient(): void {
  defaultClient = null;
}
