import type { ExceptionCategory, ExceptionQueueRowDTO } from '../ledger/types';
import { filterMarketerVisibleExceptionCategories } from '../benchmarks/benchmarkMarketingVisibility';
import type { PolicyAuthorityState } from '../lib/types';
import {
  EXCEPTION_CATEGORY_LABELS,
  EXCEPTION_POLICY_FILTER_LABELS,
  EXCEPTION_SEVERITY_LABELS,
  EXCEPTION_SOURCE_OBJECT_OPTIONS,
  EXCEPTION_STATUS_LABELS,
} from './copy';
import type { ExceptionsFilters } from './exceptionsClient';

export const EXCEPTION_CATEGORY_ORDER: ExceptionCategory[] = filterMarketerVisibleExceptionCategories([
  'discrepancy_review',
  'policy_approval_required',
  'signature_verification_failure',
  'benchmark_source_transition',
  'agent_access_denied',
  'integration_repair_needed',
]);

export function hasActiveExceptionsFilters(filters: ExceptionsFilters): boolean {
  return !!(
    filters.search ||
    (filters.category && filters.category !== 'all') ||
    (filters.severity && filters.severity !== 'all') ||
    (filters.status && filters.status !== 'all') ||
    (filters.policyAuthority && filters.policyAuthority !== 'all') ||
    (filters.sourceObject && filters.sourceObject !== 'all') ||
    filters.dateFrom ||
    filters.dateTo
  );
}

export interface ActiveExceptionFilterChip {
  key:
    | 'search'
    | 'category'
    | 'severity'
    | 'status'
    | 'policyAuthority'
    | 'sourceObject'
    | 'dateRange';
  label: string;
}

export function buildActiveExceptionFilterChips(filters: ExceptionsFilters): ActiveExceptionFilterChip[] {
  const chips: ActiveExceptionFilterChip[] = [];
  if (filters.search) chips.push({ key: 'search', label: `Search: ${filters.search}` });
  if (filters.category && filters.category !== 'all') {
    chips.push({ key: 'category', label: EXCEPTION_CATEGORY_LABELS[filters.category] });
  }
  if (filters.severity && filters.severity !== 'all') {
    chips.push({ key: 'severity', label: EXCEPTION_SEVERITY_LABELS[filters.severity] });
  }
  if (filters.status && filters.status !== 'all') {
    chips.push({ key: 'status', label: EXCEPTION_STATUS_LABELS[filters.status] });
  }
  if (filters.policyAuthority && filters.policyAuthority !== 'all') {
    chips.push({
      key: 'policyAuthority',
      label: EXCEPTION_POLICY_FILTER_LABELS[filters.policyAuthority],
    });
  }
  if (filters.sourceObject && filters.sourceObject !== 'all') {
    const label =
      EXCEPTION_SOURCE_OBJECT_OPTIONS.find((option) => option.value === filters.sourceObject)?.label ??
      filters.sourceObject;
    chips.push({ key: 'sourceObject', label });
  }
  if (filters.dateFrom || filters.dateTo) {
    chips.push({ key: 'dateRange', label: 'Last 7 days' });
  }
  return chips;
}

export function clearExceptionFilterChip(
  filters: ExceptionsFilters,
  chipKey: ActiveExceptionFilterChip['key'],
): ExceptionsFilters {
  switch (chipKey) {
    case 'search':
      return { ...filters, search: undefined, offset: 0 };
    case 'category':
      return { ...filters, category: 'all', offset: 0 };
    case 'severity':
      return { ...filters, severity: 'all', offset: 0 };
    case 'status':
      return { ...filters, status: 'all', offset: 0 };
    case 'policyAuthority':
      return { ...filters, policyAuthority: 'all', offset: 0 };
    case 'sourceObject':
      return { ...filters, sourceObject: 'all', offset: 0 };
    case 'dateRange':
      return { ...filters, dateFrom: undefined, dateTo: undefined, offset: 0 };
    default:
      return filters;
  }
}

export function matchesSourceObjectFilter(
  row: ExceptionQueueRowDTO,
  sourceObject?: ExceptionsFilters['sourceObject'],
): boolean {
  if (!sourceObject || sourceObject === 'all') return true;
  return row.sourceObjectType === sourceObject;
}

export function matchesPolicyAuthorityFilter(
  row: ExceptionQueueRowDTO,
  policyAuthority?: PolicyAuthorityState | 'all',
): boolean {
  if (!policyAuthority || policyAuthority === 'all') return true;
  return row.policyAuthority === policyAuthority;
}
