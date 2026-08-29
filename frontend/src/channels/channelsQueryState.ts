import { POLICY_AUTHORITY_STATES } from '../lib/types';
import type { ChannelsFilters } from './channelsClient';
import {
  CHANNELS_DEFAULT_PAGE_SIZE,
  CHANNELS_MAX_PAGE_SIZE,
  normalizeChannelsPageSize,
} from './channelsPagination';

export const ALLOWED_CHANNELS_METRIC_BASIS = ['verified', 'platform_claim'] as const;
export const ALLOWED_CHANNELS_ATTRIBUTION = ['under_90', 'under_80', 'all'] as const;
export const ALLOWED_CHANNELS_BAYESIAN = ['needs_review', 'healthy', 'unavailable', 'degraded'] as const;
export const ALLOWED_CHANNELS_BENCHMARK = ['attention_needed', 'stable', 'transitioning', 'unavailable'] as const;
export const ALLOWED_CHANNELS_ACTION_AUTHORITY = [
  'actionable_only',
  ...POLICY_AUTHORITY_STATES,
] as const;
export const ALLOWED_CHANNELS_SORT_KEYS = [
  'channelName',
  'attributionChannel',
  'claimSource',
  'verifiedRevenue',
  'claimedRevenue',
  'discrepancyRateBps',
  'attributionAgreement',
  'bayesianStatus',
  'benchmarkStatus',
  'policyAuthority',
] as const;

export const MAX_CHANNELS_SEARCH_LENGTH = 120;

function readParam(params: URLSearchParams, key: string): string | undefined {
  const value = params.get(key);
  return value && value.length > 0 ? value : undefined;
}

function isValidIsoDate(value: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(value));
}

export function buildChannelsQueryKey(filters: ChannelsFilters): string {
  return JSON.stringify({
    dateFrom: filters.dateFrom ?? null,
    dateTo: filters.dateTo ?? null,
    channelId: filters.channelId ?? null,
    attributionChannel: filters.attributionChannel ?? null,
    claimSource: filters.claimSource ?? null,
    commerceSource: filters.commerceSource ?? null,
    attributionAgreement: filters.attributionAgreement ?? null,
    bayesianStatus: filters.bayesianStatus ?? null,
    benchmarkStatus: filters.benchmarkStatus ?? null,
    actionAuthority: filters.actionAuthority ?? null,
    metricBasis: filters.metricBasis ?? 'verified',
    search: filters.search ?? null,
    sortKey: filters.sortKey ?? 'policyAuthority',
    sortDirection: filters.sortDirection ?? 'asc',
    offset: filters.offset ?? 0,
    pageSize: filters.pageSize ?? CHANNELS_DEFAULT_PAGE_SIZE,
  });
}

export function parseCanonicalChannelsQuery(search: string): {
  filters: ChannelsFilters;
  canonicalSearch: string;
  isCanonical: boolean;
} {
  const raw = search.startsWith('?') ? search.slice(1) : search;
  const incoming = new URLSearchParams(raw);
  const canonical = new URLSearchParams();
  let isCanonical = true;

  const setIf = (key: string, value: string | undefined) => {
    if (value) canonical.set(key, value);
  };

  const dateFrom = readParam(incoming, 'dateFrom');
  const dateTo = readParam(incoming, 'dateTo');
  if (dateFrom) {
    if (!isValidIsoDate(dateFrom)) isCanonical = false;
    else setIf('dateFrom', dateFrom);
  }
  if (dateTo) {
    if (!isValidIsoDate(dateTo)) isCanonical = false;
    else setIf('dateTo', dateTo);
  }
  if (dateFrom && dateTo && dateFrom > dateTo) isCanonical = false;

  let searchQ = readParam(incoming, 'search');
  if (searchQ) {
    if (searchQ.length > MAX_CHANNELS_SEARCH_LENGTH) {
      searchQ = searchQ.slice(0, MAX_CHANNELS_SEARCH_LENGTH);
      isCanonical = false;
    }
    setIf('search', searchQ);
  }

  const channelId = readParam(incoming, 'channelId');
  if (channelId) setIf('channelId', channelId);

  const expand = readParam(incoming, 'expand');
  if (expand) setIf('expand', expand);

  const attributionChannel = readParam(incoming, 'attributionChannel');
  if (attributionChannel) setIf('attributionChannel', attributionChannel);

  const claimSource = readParam(incoming, 'claimSource');
  if (claimSource) setIf('claimSource', claimSource);

  const commerceSource = readParam(incoming, 'commerceSource');
  if (commerceSource) setIf('commerceSource', commerceSource);

  const attributionAgreement = readParam(incoming, 'attributionAgreement');
  if (attributionAgreement) {
    if (!ALLOWED_CHANNELS_ATTRIBUTION.includes(attributionAgreement as (typeof ALLOWED_CHANNELS_ATTRIBUTION)[number])) {
      isCanonical = false;
    } else if (attributionAgreement !== 'all') {
      setIf('attributionAgreement', attributionAgreement);
    }
  }

  const bayesianStatus = readParam(incoming, 'bayesianStatus');
  if (bayesianStatus) {
    if (!ALLOWED_CHANNELS_BAYESIAN.includes(bayesianStatus as (typeof ALLOWED_CHANNELS_BAYESIAN)[number])) {
      isCanonical = false;
    } else {
      setIf('bayesianStatus', bayesianStatus);
    }
  }

  const benchmarkStatus = readParam(incoming, 'benchmarkStatus');
  if (benchmarkStatus) {
    if (!ALLOWED_CHANNELS_BENCHMARK.includes(benchmarkStatus as (typeof ALLOWED_CHANNELS_BENCHMARK)[number])) {
      isCanonical = false;
    } else {
      setIf('benchmarkStatus', benchmarkStatus);
    }
  }

  const actionAuthority = readParam(incoming, 'actionAuthority');
  if (actionAuthority) {
    if (!ALLOWED_CHANNELS_ACTION_AUTHORITY.includes(actionAuthority as (typeof ALLOWED_CHANNELS_ACTION_AUTHORITY)[number])) {
      isCanonical = false;
    } else {
      setIf('actionAuthority', actionAuthority);
    }
  }

  const metricBasis = readParam(incoming, 'metricBasis') ?? 'verified';
  if (!ALLOWED_CHANNELS_METRIC_BASIS.includes(metricBasis as (typeof ALLOWED_CHANNELS_METRIC_BASIS)[number])) {
    isCanonical = false;
    canonical.set('metricBasis', 'verified');
  } else if (metricBasis !== 'verified') {
    setIf('metricBasis', metricBasis);
  }

  const sortKeyRaw = readParam(incoming, 'sortKey') ?? 'policyAuthority';
  const sortKey = ALLOWED_CHANNELS_SORT_KEYS.includes(sortKeyRaw as (typeof ALLOWED_CHANNELS_SORT_KEYS)[number])
    ? sortKeyRaw
    : 'policyAuthority';
  if (sortKeyRaw !== sortKey) {
    isCanonical = false;
    canonical.set('sortKey', sortKey);
  } else if (sortKey !== 'policyAuthority') {
    setIf('sortKey', sortKey);
  }

  const sortDirectionRaw = readParam(incoming, 'sortDirection') ?? 'asc';
  const sortDirection = sortDirectionRaw === 'desc' ? 'desc' : 'asc';
  if (sortDirectionRaw !== sortDirection) {
    isCanonical = false;
    canonical.set('sortDirection', sortDirection);
  } else if (sortDirection !== 'asc') {
    setIf('sortDirection', sortDirection);
  }

  const offsetRaw = readParam(incoming, 'offset');
  let offset = 0;
  if (offsetRaw) {
    const parsed = Number.parseInt(offsetRaw, 10);
    if (!Number.isFinite(parsed) || parsed < 0) isCanonical = false;
    else {
      offset = parsed;
      if (offset > 0) setIf('offset', String(offset));
    }
  }

  const pageSizeRaw = readParam(incoming, 'pageSize');
  let pageSize = CHANNELS_DEFAULT_PAGE_SIZE;
  if (pageSizeRaw) {
    const parsed = Number.parseInt(pageSizeRaw, 10);
    if (!Number.isFinite(parsed) || parsed < 1 || parsed > CHANNELS_MAX_PAGE_SIZE) isCanonical = false;
    else {
      pageSize = normalizeChannelsPageSize(parsed);
      if (pageSize !== CHANNELS_DEFAULT_PAGE_SIZE) setIf('pageSize', String(pageSize));
    }
  }

  const filters: ChannelsFilters = {
    dateFrom,
    dateTo,
    channelId,
    attributionChannel,
    claimSource,
    commerceSource,
    attributionAgreement: attributionAgreement as ChannelsFilters['attributionAgreement'],
    bayesianStatus: bayesianStatus as ChannelsFilters['bayesianStatus'],
    benchmarkStatus: benchmarkStatus as ChannelsFilters['benchmarkStatus'],
    actionAuthority: actionAuthority as ChannelsFilters['actionAuthority'],
    metricBasis: metricBasis as ChannelsFilters['metricBasis'],
    search: searchQ,
    sortKey,
    sortDirection: sortDirection as 'asc' | 'desc',
    offset,
    pageSize,
  };

  const canonicalSearch = canonical.toString();
  const rawCanonical = new URLSearchParams(raw);
  rawCanonical.sort();
  const sortedIncoming = [...rawCanonical.entries()].sort(([a], [b]) => a.localeCompare(b));
  const sortedCanonical = [...canonical.entries()].sort(([a], [b]) => a.localeCompare(b));
  if (JSON.stringify(sortedIncoming) !== JSON.stringify(sortedCanonical)) {
    isCanonical = false;
  }

  return { filters, canonicalSearch: canonicalSearch ? `?${canonicalSearch}` : '', isCanonical };
}

export function channelsFiltersToSearchParams(filters: ChannelsFilters): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.dateFrom) params.set('dateFrom', filters.dateFrom);
  if (filters.dateTo) params.set('dateTo', filters.dateTo);
  if (filters.channelId) params.set('channelId', filters.channelId);
  if (filters.attributionChannel) params.set('attributionChannel', filters.attributionChannel);
  if (filters.claimSource) params.set('claimSource', filters.claimSource);
  if (filters.commerceSource) params.set('commerceSource', filters.commerceSource);
  if (filters.attributionAgreement && filters.attributionAgreement !== 'all') {
    params.set('attributionAgreement', filters.attributionAgreement);
  }
  if (filters.bayesianStatus) params.set('bayesianStatus', filters.bayesianStatus);
  if (filters.benchmarkStatus) params.set('benchmarkStatus', filters.benchmarkStatus);
  if (filters.actionAuthority) params.set('actionAuthority', filters.actionAuthority);
  if (filters.metricBasis && filters.metricBasis !== 'verified') params.set('metricBasis', filters.metricBasis);
  if (filters.search) params.set('search', filters.search);
  if (filters.sortKey && filters.sortKey !== 'policyAuthority') params.set('sortKey', filters.sortKey);
  if (filters.sortDirection && filters.sortDirection !== 'asc') params.set('sortDirection', filters.sortDirection);
  if (filters.offset) params.set('offset', String(filters.offset));
  if (filters.pageSize && filters.pageSize !== CHANNELS_DEFAULT_PAGE_SIZE) {
    params.set('pageSize', String(filters.pageSize));
  }
  return params;
}

/** Preserve UI-only `expand` when rewriting filter query strings. */
export function appendChannelsExpandParam(
  params: URLSearchParams,
  expandChannelId: string | null | undefined,
): URLSearchParams {
  if (expandChannelId) params.set('expand', expandChannelId);
  else params.delete('expand');
  return params;
}
