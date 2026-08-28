import type { ClaimsFilters } from '../claims/claimsClient';
import {
  CLAIMS_LEDGER_DEFAULT_PAGE_SIZE,
  isAllowedClaimsPageSize,
  normalizeClaimsPageSize,
} from '../claims/claimsPagination';
import { POLICY_AUTHORITY_STATES } from '../lib/types';
import type { DiscrepancyClass } from './types';

export const ALLOWED_CLAIM_SORT_KEYS = ['lastUpdated', 'discrepancy', 'verificationStatus', 'date'] as const;
export const ALLOWED_CLAIM_SOURCES = ['meta_ads', 'google_ads', 'tiktok_ads', 'linkedin_ads'] as const;
export const ALLOWED_CAMPAIGN_CLASSES = [
  'paid_search',
  'paid_social',
  'creator',
  'branded',
  'affiliate',
] as const;
export const ALLOWED_COMMERCE_RAILS = ['organic', 'direct', 'referral', 'email'] as const;
export const ALLOWED_COMMERCE_SOURCES = ['shopify', 'stripe'] as const;
export const ALLOWED_VERIFICATION_STATUSES = ['verified', 'partial', 'unverified'] as const;
export const ALLOWED_DISCREPANCY_CLASSES: readonly DiscrepancyClass[] = [
  'within_tolerance',
  'flagged',
  'material',
] as const;
export const ALLOWED_POLICY_AUTHORITY = POLICY_AUTHORITY_STATES;
export const MAX_CLAIM_SEARCH_LENGTH = 120;

function readParam(params: URLSearchParams, key: string): string | undefined {
  const value = params.get(key);
  return value && value.length > 0 ? value : undefined;
}

function isValidIsoDate(value: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(value));
}

export interface ClaimsDrillContext {
  trendDrill?: boolean;
  trendWindowLabel?: string;
  windowStart?: string;
  windowEnd?: string;
}

function isValidIsoDateTime(value: string): boolean {
  return !Number.isNaN(Date.parse(value));
}

export function buildClaimsQueryKey(filters: ClaimsFilters): string {
  return JSON.stringify({
    dateFrom: filters.dateFrom ?? null,
    dateTo: filters.dateTo ?? null,
    windowStart: filters.windowStart ?? null,
    windowEnd: filters.windowEnd ?? null,
    trendDrill: filters.trendDrill ?? null,
    trendWindowLabel: filters.trendWindowLabel ?? null,
    claimSource: filters.claimSource ?? null,
    campaignClass: filters.campaignClass ?? null,
    commerceRail: filters.commerceRail ?? null,
    commerceSource: filters.commerceSource ?? null,
    verificationStatus: filters.verificationStatus ?? null,
    discrepancyClass: filters.discrepancyClass ?? null,
    policyAuthority: filters.policyAuthority ?? null,
    search: filters.search ?? null,
    sortKey: filters.sortKey ?? 'lastUpdated',
    sortDirection: filters.sortDirection ?? 'desc',
    offset: filters.offset ?? 0,
    pageSize: filters.pageSize ?? CLAIMS_LEDGER_DEFAULT_PAGE_SIZE,
  });
}

export function parseCanonicalClaimsQuery(search: string): {
  filters: ClaimsFilters;
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

  const windowStart = readParam(incoming, 'windowStart');
  const windowEnd = readParam(incoming, 'windowEnd');
  if (windowStart) {
    if (!isValidIsoDateTime(windowStart)) isCanonical = false;
    else setIf('windowStart', windowStart);
  }
  if (windowEnd) {
    if (!isValidIsoDateTime(windowEnd)) isCanonical = false;
    else setIf('windowEnd', windowEnd);
  }
  if (windowStart && windowEnd && Date.parse(windowStart) >= Date.parse(windowEnd)) {
    isCanonical = false;
  }

  const trendDrillRaw = readParam(incoming, 'trendDrill');
  let trendDrill = false;
  if (trendDrillRaw) {
    if (trendDrillRaw === '1' || trendDrillRaw === 'true') {
      trendDrill = true;
      canonical.set('trendDrill', '1');
    } else {
      isCanonical = false;
    }
  }

  const trendWindowLabel = readParam(incoming, 'trendWindowLabel');
  if (trendWindowLabel) {
    if (trendWindowLabel.length > 120) isCanonical = false;
    else setIf('trendWindowLabel', trendWindowLabel);
  }

  const claimSource = readParam(incoming, 'claimSource');
  if (claimSource) {
    if (!ALLOWED_CLAIM_SOURCES.includes(claimSource as (typeof ALLOWED_CLAIM_SOURCES)[number])) {
      isCanonical = false;
    } else {
      setIf('claimSource', claimSource);
    }
  }

  const campaignClass = readParam(incoming, 'campaignClass');
  if (campaignClass) {
    if (!ALLOWED_CAMPAIGN_CLASSES.includes(campaignClass as (typeof ALLOWED_CAMPAIGN_CLASSES)[number])) {
      isCanonical = false;
    } else {
      setIf('campaignClass', campaignClass);
    }
  }

  const commerceRail = readParam(incoming, 'commerceRail');
  if (commerceRail) {
    if (!ALLOWED_COMMERCE_RAILS.includes(commerceRail as (typeof ALLOWED_COMMERCE_RAILS)[number])) {
      isCanonical = false;
    } else {
      setIf('commerceRail', commerceRail);
    }
  }

  const commerceSource = readParam(incoming, 'commerceSource');
  if (commerceSource) {
    if (!ALLOWED_COMMERCE_SOURCES.includes(commerceSource as (typeof ALLOWED_COMMERCE_SOURCES)[number])) {
      isCanonical = false;
    } else {
      setIf('commerceSource', commerceSource);
    }
  }

  const verificationStatus = readParam(incoming, 'verificationStatus');
  if (verificationStatus) {
    if (!ALLOWED_VERIFICATION_STATUSES.includes(verificationStatus as (typeof ALLOWED_VERIFICATION_STATUSES)[number])) {
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
    if (!ALLOWED_POLICY_AUTHORITY.includes(policyAuthority as (typeof ALLOWED_POLICY_AUTHORITY)[number])) {
      isCanonical = false;
    } else {
      setIf('policyAuthority', policyAuthority);
    }
  }

  let searchQ = readParam(incoming, 'search');
  if (searchQ) {
    if (searchQ.length > MAX_CLAIM_SEARCH_LENGTH) {
      searchQ = searchQ.slice(0, MAX_CLAIM_SEARCH_LENGTH);
      isCanonical = false;
    }
    setIf('search', searchQ);
  }

  const sortRaw = readParam(incoming, 'sort') ?? 'lastUpdated';
  const sortKey = ALLOWED_CLAIM_SORT_KEYS.includes(sortRaw as (typeof ALLOWED_CLAIM_SORT_KEYS)[number])
    ? sortRaw
    : 'lastUpdated';
  if (sortRaw !== sortKey) isCanonical = false;
  canonical.set('sort', sortKey);

  const sortDirRaw = readParam(incoming, 'sortDir') ?? 'desc';
  const sortDirection = sortDirRaw === 'asc' || sortDirRaw === 'desc' ? sortDirRaw : 'desc';
  if (sortDirRaw !== sortDirection) isCanonical = false;
  canonical.set('sortDir', sortDirection);

  const offsetRaw = incoming.get('offset');
  let offset = 0;
  if (offsetRaw !== null && offsetRaw !== '') {
    const parsed = parseInt(offsetRaw, 10);
    if (!Number.isFinite(parsed) || parsed < 0 || String(parsed) !== offsetRaw.trim()) {
      isCanonical = false;
      offset = 0;
    } else {
      offset = parsed;
      if (offset > 0) canonical.set('offset', String(offset));
    }
  }

  const pageSizeRaw = incoming.get('pageSize');
  let pageSize = CLAIMS_LEDGER_DEFAULT_PAGE_SIZE;
  if (pageSizeRaw !== null && pageSizeRaw !== '') {
    const parsed = parseInt(pageSizeRaw, 10);
    if (!Number.isFinite(parsed) || parsed < 1) {
      isCanonical = false;
      pageSize = CLAIMS_LEDGER_DEFAULT_PAGE_SIZE;
    } else {
      pageSize = normalizeClaimsPageSize(parsed);
      if (String(pageSize) !== pageSizeRaw.trim() || !isAllowedClaimsPageSize(parsed)) {
        isCanonical = false;
      }
      if (pageSize !== CLAIMS_LEDGER_DEFAULT_PAGE_SIZE) {
        canonical.set('pageSize', String(pageSize));
      }
    }
  }

  for (const key of incoming.keys()) {
    const known = new Set([
      'dateFrom',
      'dateTo',
      'windowStart',
      'windowEnd',
      'trendDrill',
      'trendWindowLabel',
      'claimSource',
      'campaignClass',
      'commerceRail',
      'commerceSource',
      'verificationStatus',
      'discrepancyClass',
      'policyAuthority',
      'search',
      'sort',
      'sortDir',
      'offset',
      'pageSize',
    ]);
    if (!known.has(key)) isCanonical = false;
  }

  const filters: ClaimsFilters = {
    dateFrom: canonical.get('dateFrom') ?? undefined,
    dateTo: canonical.get('dateTo') ?? undefined,
    windowStart: canonical.get('windowStart') ?? undefined,
    windowEnd: canonical.get('windowEnd') ?? undefined,
    trendDrill: trendDrill || undefined,
    trendWindowLabel: canonical.get('trendWindowLabel') ?? undefined,
    claimSource: canonical.get('claimSource') ?? undefined,
    campaignClass: canonical.get('campaignClass') ?? undefined,
    commerceRail: canonical.get('commerceRail') ?? undefined,
    commerceSource: canonical.get('commerceSource') ?? undefined,
    verificationStatus: canonical.get('verificationStatus') ?? undefined,
    discrepancyClass: canonical.get('discrepancyClass') ?? undefined,
    policyAuthority: canonical.get('policyAuthority') ?? undefined,
    search: canonical.get('search') ?? undefined,
    sortKey,
    sortDirection,
    offset: offset > 0 ? offset : undefined,
    pageSize: pageSize !== CLAIMS_LEDGER_DEFAULT_PAGE_SIZE ? pageSize : undefined,
  };

  const canonicalString = canonical.toString();
  return {
    filters,
    canonicalSearch: canonicalString ? `?${canonicalString}` : '',
    isCanonical,
  };
}

export function claimsFiltersToSearchParams(filters: ClaimsFilters): URLSearchParams {
  const { canonicalSearch } = parseCanonicalClaimsQuery(
    `?${new URLSearchParams({
      ...(filters.dateFrom ? { dateFrom: filters.dateFrom } : {}),
      ...(filters.dateTo ? { dateTo: filters.dateTo } : {}),
      ...(filters.windowStart ? { windowStart: filters.windowStart } : {}),
      ...(filters.windowEnd ? { windowEnd: filters.windowEnd } : {}),
      ...(filters.trendDrill ? { trendDrill: '1' } : {}),
      ...(filters.trendWindowLabel ? { trendWindowLabel: filters.trendWindowLabel } : {}),
      ...(filters.claimSource ? { claimSource: filters.claimSource } : {}),
      ...(filters.campaignClass ? { campaignClass: filters.campaignClass } : {}),
      ...(filters.commerceRail ? { commerceRail: filters.commerceRail } : {}),
      ...(filters.commerceSource ? { commerceSource: filters.commerceSource } : {}),
      ...(filters.verificationStatus ? { verificationStatus: filters.verificationStatus } : {}),
      ...(filters.discrepancyClass ? { discrepancyClass: filters.discrepancyClass } : {}),
      ...(filters.policyAuthority ? { policyAuthority: filters.policyAuthority } : {}),
      ...(filters.search ? { search: filters.search } : {}),
      sort: filters.sortKey ?? 'lastUpdated',
      sortDir: filters.sortDirection ?? 'desc',
      ...(filters.offset ? { offset: String(filters.offset) } : {}),
      ...(filters.pageSize ? { pageSize: String(filters.pageSize) } : {}),
    }).toString()}`,
  );
  return new URLSearchParams(canonicalSearch.startsWith('?') ? canonicalSearch.slice(1) : canonicalSearch);
}
