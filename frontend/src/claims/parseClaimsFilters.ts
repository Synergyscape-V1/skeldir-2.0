import type { ClaimsFilters } from './claimsClient';
import {
  parseCanonicalClaimsQuery,
  claimsFiltersToSearchParams as serializeClaimsFilters,
  buildClaimsQueryKey,
} from '../ledger/claimsQueryState';

export { buildClaimsQueryKey, parseCanonicalClaimsQuery };

export function parseClaimsFilters(search: string): ClaimsFilters {
  return parseCanonicalClaimsQuery(search).filters;
}

export function claimsFiltersToSearchParams(filters: ClaimsFilters): URLSearchParams {
  return serializeClaimsFilters(filters);
}
