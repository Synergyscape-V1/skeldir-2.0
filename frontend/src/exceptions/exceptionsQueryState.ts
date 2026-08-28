import type { ExceptionCategory, ExceptionSeverity } from '../ledger/types';
import type { PolicyAuthorityState } from '../lib/types';
import { isMarketerHiddenExceptionCategory } from '../benchmarks/benchmarkMarketingVisibility';
import {
  EXCEPTION_DEFAULT_DATE_FROM,
  EXCEPTION_DEFAULT_DATE_TO,
} from './exceptionsFixtures';
import {
  EXCEPTIONS_DEFAULT_PAGE_SIZE,
  EXCEPTIONS_MAX_PAGE_SIZE,
  normalizeExceptionsPageSize,
} from './exceptionsPagination';
import type { ExceptionsFilters } from './exceptionsClient';

export const ALLOWED_EXCEPTION_SORT_KEYS = ['createdAt', 'severity', 'category', 'status'] as const;

const ALLOWED_CATEGORIES = new Set<ExceptionCategory>([
  'discrepancy_review',
  'policy_approval_required',
  'signature_verification_failure',
  'benchmark_source_transition',
  'agent_access_denied',
  'integration_repair_needed',
]);

const ALLOWED_SEVERITIES = new Set<ExceptionSeverity>(['critical', 'warning', 'info']);
const ALLOWED_STATUSES = new Set(['open', 'acknowledged', 'suppressed', 'resolved']);

function readParam(params: URLSearchParams, key: string): string | undefined {
  const value = params.get(key);
  return value && value.length > 0 ? value : undefined;
}

function isValidIsoDate(value: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(value));
}

export function exceptionsDefaultFilters(): ExceptionsFilters {
  return {
    dateFrom: EXCEPTION_DEFAULT_DATE_FROM,
    dateTo: EXCEPTION_DEFAULT_DATE_TO,
    category: 'all',
    severity: 'all',
    status: 'all',
    policyAuthority: 'all',
    sourceObject: 'all',
    offset: 0,
    pageSize: EXCEPTIONS_DEFAULT_PAGE_SIZE,
    sortKey: 'createdAt',
    sortDirection: 'desc',
  };
}

export function buildExceptionsQueryKey(filters: ExceptionsFilters): string {
  return JSON.stringify({
    dateFrom: filters.dateFrom ?? null,
    dateTo: filters.dateTo ?? null,
    category: filters.category ?? 'all',
    severity: filters.severity ?? 'all',
    status: filters.status ?? 'all',
    policyAuthority: filters.policyAuthority ?? 'all',
    sourceObject: filters.sourceObject ?? 'all',
    search: filters.search ?? null,
    sortKey: filters.sortKey ?? 'createdAt',
    sortDirection: filters.sortDirection ?? 'desc',
    offset: filters.offset ?? 0,
    pageSize: filters.pageSize ?? EXCEPTIONS_DEFAULT_PAGE_SIZE,
  });
}

export function parseExceptionsFilters(search: string): ExceptionsFilters {
  const raw = search.startsWith('?') ? search.slice(1) : search;
  const params = new URLSearchParams(raw);
  const defaults = exceptionsDefaultFilters();

  if (!raw) return defaults;

  const dateFrom = readParam(params, 'dateFrom');
  const dateTo = readParam(params, 'dateTo');
  const categoryRaw = readParam(params, 'category');
  const severityRaw = readParam(params, 'severity');
  const statusRaw = readParam(params, 'status');
  const policyRaw = readParam(params, 'policyAuthority');
  const sourceObject = readParam(params, 'sourceObject');
  const searchText = readParam(params, 'search');
  const sortKey = readParam(params, 'sortKey');
  const sortDirection = readParam(params, 'sortDirection');
  const offsetRaw = readParam(params, 'offset');
  const pageSizeRaw = readParam(params, 'pageSize');

  const category =
    categoryRaw &&
    (categoryRaw === 'all' ||
      (ALLOWED_CATEGORIES.has(categoryRaw as ExceptionCategory) &&
        !isMarketerHiddenExceptionCategory(categoryRaw as ExceptionCategory)))
      ? (categoryRaw as ExceptionsFilters['category'])
      : categoryRaw && isMarketerHiddenExceptionCategory(categoryRaw as ExceptionCategory)
        ? 'all'
        : defaults.category;

  const severity =
    severityRaw && (severityRaw === 'all' || ALLOWED_SEVERITIES.has(severityRaw as ExceptionSeverity))
      ? (severityRaw as ExceptionsFilters['severity'])
      : defaults.severity;

  const status =
    statusRaw && (statusRaw === 'all' || ALLOWED_STATUSES.has(statusRaw))
      ? (statusRaw as ExceptionsFilters['status'])
      : defaults.status;

  const policyAuthority =
    policyRaw && policyRaw !== 'all'
      ? (policyRaw as PolicyAuthorityState)
      : defaults.policyAuthority;

  const parsedOffset = offsetRaw ? Number.parseInt(offsetRaw, 10) : 0;
  const parsedPageSize = pageSizeRaw ? Number.parseInt(pageSizeRaw, 10) : EXCEPTIONS_DEFAULT_PAGE_SIZE;

  return {
    dateFrom: dateFrom && isValidIsoDate(dateFrom) ? dateFrom : defaults.dateFrom,
    dateTo: dateTo && isValidIsoDate(dateTo) ? dateTo : defaults.dateTo,
    category,
    severity,
    status,
    policyAuthority,
    sourceObject: sourceObject ?? defaults.sourceObject,
    search: searchText,
    sortKey:
      sortKey && ALLOWED_EXCEPTION_SORT_KEYS.includes(sortKey as (typeof ALLOWED_EXCEPTION_SORT_KEYS)[number])
        ? sortKey
        : defaults.sortKey,
    sortDirection: sortDirection === 'asc' ? 'asc' : 'desc',
    offset: Number.isFinite(parsedOffset) && parsedOffset >= 0 ? parsedOffset : 0,
    pageSize: normalizeExceptionsPageSize(
      Number.isFinite(parsedPageSize) ? Math.min(parsedPageSize, EXCEPTIONS_MAX_PAGE_SIZE) : undefined,
    ),
  };
}

export function exceptionsFiltersToSearchParams(filters: ExceptionsFilters): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.dateFrom) params.set('dateFrom', filters.dateFrom);
  if (filters.dateTo) params.set('dateTo', filters.dateTo);
  if (filters.category && filters.category !== 'all') params.set('category', filters.category);
  if (filters.severity && filters.severity !== 'all') params.set('severity', filters.severity);
  if (filters.status && filters.status !== 'all') params.set('status', filters.status);
  if (filters.policyAuthority && filters.policyAuthority !== 'all') {
    params.set('policyAuthority', filters.policyAuthority);
  }
  if (filters.sourceObject && filters.sourceObject !== 'all') params.set('sourceObject', filters.sourceObject);
  if (filters.search) params.set('search', filters.search);
  if (filters.sortKey) params.set('sortKey', filters.sortKey);
  if (filters.sortDirection) params.set('sortDirection', filters.sortDirection);
  if (filters.offset) params.set('offset', String(filters.offset));
  if (filters.pageSize && filters.pageSize !== EXCEPTIONS_DEFAULT_PAGE_SIZE) {
    params.set('pageSize', String(filters.pageSize));
  }
  return params;
}

export function parseCanonicalExceptionsQuery(search: string): {
  isCanonical: boolean;
  canonicalSearch: string;
} {
  const parsed = parseExceptionsFilters(search);
  const canonical = exceptionsFiltersToSearchParams(parsed);
  const canonicalSearch = canonical.toString() ? `?${canonical.toString()}` : '';
  const normalizedInput = search.startsWith('?') ? search : search ? `?${search}` : '';
  return { isCanonical: normalizedInput === canonicalSearch, canonicalSearch };
}
