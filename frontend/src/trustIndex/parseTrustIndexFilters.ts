import {
  buildTrustIndexQueryKey,
  parseCanonicalTrustIndexQuery,
  trustIndexFiltersToSearchParams,
} from './trustIndexQueryState';
import type { TrustIndexFilters } from './trustIndexClient';

export { buildTrustIndexQueryKey, parseCanonicalTrustIndexQuery };

export function parseTrustIndexFilters(search: string): TrustIndexFilters {
  return parseCanonicalTrustIndexQuery(search).filters;
}

export function trustIndexFiltersToSearch(filters: TrustIndexFilters): string {
  const params = trustIndexFiltersToSearchParams(filters);
  const serialized = params.toString();
  return serialized ? `?${serialized}` : '';
}
