import { POLICY_AUTHORITY_STATES } from '../lib/types';
import type { BenchmarkEvidenceClass, DiscrepancyClass } from '../ledger/types';
import { ALLOWED_DISCREPANCY_CLASSES } from '../ledger/claimsQueryState';
import type { TrustIndexFilters } from './trustIndexClient';
import { TRUST_INDEX_DEFAULT_SORT_KEY } from './trustIndexEnvelopeDisplay';

export const TRUST_INDEX_DEFAULT_PAGE_SIZE = 10;
export const TRUST_INDEX_MAX_PAGE_SIZE = 10;

export const ALLOWED_TRUST_VERIFICATION_STATUSES = [
  'verified',
  'partial',
  'unverified',
  'disputed',
] as const;

export const ALLOWED_TRUST_CONFIDENCE_AVAILABILITY = ['available', 'unavailable'] as const;

export const ALLOWED_TRUST_BENCHMARK_SOURCES: readonly BenchmarkEvidenceClass[] = [
  'live_empirical',
  'tenant_longitudinal',
  'historical_prior',
  'public_prior',
  'unavailable',
] as const;

export const ALLOWED_TRUST_SORT_KEYS = [
  TRUST_INDEX_DEFAULT_SORT_KEY,
  'claimTime',
  'discrepancyRateBps',
  'policyAuthority',
] as const;

function readParam(params: URLSearchParams, key: string): string | undefined {
  const value = params.get(key);
  return value && value.length > 0 ? value : undefined;
}

export function buildTrustIndexQueryKey(filters: TrustIndexFilters): string {
  return JSON.stringify({
    verificationStatus: filters.verificationStatus ?? null,
    discrepancyClass: filters.discrepancyClass ?? null,
    policyAuthority: filters.policyAuthority ?? null,
    confidenceAvailability: filters.confidenceAvailability ?? null,
    benchmarkSource: filters.benchmarkSource ?? null,
    status: filters.status ?? null,
    sortKey: filters.sortKey ?? TRUST_INDEX_DEFAULT_SORT_KEY,
    sortDirection: filters.sortDirection ?? 'desc',
    offset: filters.offset ?? 0,
    pageSize: filters.pageSize ?? TRUST_INDEX_DEFAULT_PAGE_SIZE,
  });
}

export function parseCanonicalTrustIndexQuery(search: string): {
  filters: TrustIndexFilters;
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

  const verificationStatus = readParam(incoming, 'verificationStatus');
  if (verificationStatus) {
    if (
      !ALLOWED_TRUST_VERIFICATION_STATUSES.includes(
        verificationStatus as (typeof ALLOWED_TRUST_VERIFICATION_STATUSES)[number],
      )
    ) {
      isCanonical = false;
    } else {
      setIf('verificationStatus', verificationStatus);
    }
  }

  const discrepancyClass = readParam(incoming, 'discrepancyClass');
  if (discrepancyClass) {
    if (!ALLOWED_DISCREPANCY_CLASSES.includes(discrepancyClass as DiscrepancyClass)) {
      isCanonical = false;
    } else {
      setIf('discrepancyClass', discrepancyClass);
    }
  }

  const policyAuthority = readParam(incoming, 'policyAuthority');
  if (policyAuthority) {
    if (!POLICY_AUTHORITY_STATES.includes(policyAuthority as (typeof POLICY_AUTHORITY_STATES)[number])) {
      isCanonical = false;
    } else {
      setIf('policyAuthority', policyAuthority);
    }
  }

  const confidenceAvailability = readParam(incoming, 'confidenceAvailability');
  if (confidenceAvailability) {
    if (
      !ALLOWED_TRUST_CONFIDENCE_AVAILABILITY.includes(
        confidenceAvailability as (typeof ALLOWED_TRUST_CONFIDENCE_AVAILABILITY)[number],
      )
    ) {
      isCanonical = false;
    } else {
      setIf('confidenceAvailability', confidenceAvailability);
    }
  }

  const benchmarkSource = readParam(incoming, 'benchmarkSource');
  if (benchmarkSource) {
    if (!ALLOWED_TRUST_BENCHMARK_SOURCES.includes(benchmarkSource as BenchmarkEvidenceClass)) {
      isCanonical = false;
    } else {
      setIf('benchmarkSource', benchmarkSource);
    }
  }

  const status = readParam(incoming, 'status');
  if (status) setIf('status', status);

  const sortRaw = readParam(incoming, 'sort') ?? TRUST_INDEX_DEFAULT_SORT_KEY;
  const sortKey = sortRaw === 'date' || sortRaw === 'generationTimestamp' ? 'claimTime' : sortRaw;
  if (!ALLOWED_TRUST_SORT_KEYS.includes(sortKey as (typeof ALLOWED_TRUST_SORT_KEYS)[number])) {
    isCanonical = false;
  }
  if (sortKey !== TRUST_INDEX_DEFAULT_SORT_KEY) setIf('sort', sortKey);

  const sortDirection = readParam(incoming, 'sortDirection') ?? 'desc';
  if (sortDirection !== 'asc' && sortDirection !== 'desc') isCanonical = false;
  else if (sortDirection !== 'desc') setIf('sortDirection', sortDirection);

  const legacyKeys = [
    'search',
    'dateFrom',
    'dateTo',
    'authorityClass',
    'signatureStatus',
    'confidenceStatus',
    'benchmarkEvidence',
    'channelSource',
    'savedView',
    'density',
  ];
  for (const key of legacyKeys) {
    if (incoming.has(key)) isCanonical = false;
  }

  let offset = 0;
  const offsetRaw = readParam(incoming, 'offset');
  if (offsetRaw) {
    const parsed = parseInt(offsetRaw, 10);
    if (!Number.isFinite(parsed) || parsed < 0) isCanonical = false;
    else {
      offset = parsed;
      if (offset > 0) setIf('offset', String(offset));
    }
  }

  let pageSize = TRUST_INDEX_DEFAULT_PAGE_SIZE;
  const pageSizeRaw = readParam(incoming, 'pageSize');
  if (pageSizeRaw) {
    const parsed = parseInt(pageSizeRaw, 10);
    if (!Number.isFinite(parsed) || parsed < 1 || parsed > TRUST_INDEX_MAX_PAGE_SIZE) isCanonical = false;
    else {
      pageSize = parsed;
      if (pageSize !== TRUST_INDEX_DEFAULT_PAGE_SIZE) setIf('pageSize', String(pageSize));
    }
  }

  const filters: TrustIndexFilters = {
    verificationStatus: verificationStatus as TrustIndexFilters['verificationStatus'],
    discrepancyClass: discrepancyClass as DiscrepancyClass,
    policyAuthority: policyAuthority as TrustIndexFilters['policyAuthority'],
    confidenceAvailability: confidenceAvailability as TrustIndexFilters['confidenceAvailability'],
    benchmarkSource: benchmarkSource as BenchmarkEvidenceClass,
    status,
    sortKey,
    sortDirection: sortDirection as 'asc' | 'desc',
    offset,
    pageSize,
  };

  const canonicalSearch = canonical.toString();
  if (canonicalSearch !== raw) isCanonical = false;

  return { filters, canonicalSearch: canonicalSearch ? `?${canonicalSearch}` : '', isCanonical };
}

export function trustIndexFiltersToSearchParams(filters: TrustIndexFilters): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.verificationStatus) params.set('verificationStatus', filters.verificationStatus);
  if (filters.discrepancyClass) params.set('discrepancyClass', filters.discrepancyClass);
  if (filters.policyAuthority) params.set('policyAuthority', filters.policyAuthority);
  if (filters.confidenceAvailability) params.set('confidenceAvailability', filters.confidenceAvailability);
  if (filters.benchmarkSource) params.set('benchmarkSource', filters.benchmarkSource);
  if (filters.status) params.set('status', filters.status);
  if (filters.sortKey && filters.sortKey !== TRUST_INDEX_DEFAULT_SORT_KEY) params.set('sort', filters.sortKey);
  if (filters.sortDirection && filters.sortDirection !== 'desc') params.set('sortDirection', filters.sortDirection);
  if (filters.offset) params.set('offset', String(filters.offset));
  if (filters.pageSize && filters.pageSize !== TRUST_INDEX_DEFAULT_PAGE_SIZE) {
    params.set('pageSize', String(filters.pageSize));
  }
  return params;
}

/** CTA target: isolate envelopes with unavailable confidence on the TrustEnvelope index. */
export function buildUnavailableConfidenceIsolateHref(filters: TrustIndexFilters): string {
  const params = trustIndexFiltersToSearchParams({
    ...filters,
    confidenceAvailability: 'unavailable',
    offset: 0,
  });
  const search = params.toString();
  return search ? `/app/trust?${search}` : '/app/trust?confidenceAvailability=unavailable';
}

/** Clear only the confidenceAvailability filter while preserving other index filters. */
export function buildClearConfidenceAvailabilityHref(filters: TrustIndexFilters): string {
  const params = trustIndexFiltersToSearchParams({
    ...filters,
    confidenceAvailability: undefined,
    offset: 0,
  });
  const search = params.toString();
  return search ? `/app/trust?${search}` : '/app/trust';
}
