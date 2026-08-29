import { describe, expect, it } from 'vitest';
import {
  CLAIMS_LEDGER_DEFAULT_PAGE_SIZE,
  CLAIMS_LEDGER_MAX_PAGE_SIZE,
  CLAIMS_LEDGER_MIN_PAGE_SIZE,
  isAllowedClaimsPageSize,
  normalizeClaimsPageSize,
} from '../claims/claimsPagination';
import { parseCanonicalClaimsQuery } from '../ledger/claimsQueryState';

describe('claimsPagination', () => {
  it('defaults to 10 rows within the supervisory 6–10 window', () => {
    expect(normalizeClaimsPageSize()).toBe(10);
    expect(CLAIMS_LEDGER_DEFAULT_PAGE_SIZE).toBe(10);
    expect(CLAIMS_LEDGER_MIN_PAGE_SIZE).toBe(6);
    expect(CLAIMS_LEDGER_MAX_PAGE_SIZE).toBe(10);
  });

  it('clamps out-of-range page sizes into the allowed window', () => {
    expect(normalizeClaimsPageSize(25)).toBe(10);
    expect(normalizeClaimsPageSize(3)).toBe(6);
    expect(normalizeClaimsPageSize(8)).toBe(8);
  });

  it('allows only integer sizes between 6 and 10 inclusive', () => {
    expect(isAllowedClaimsPageSize(6)).toBe(true);
    expect(isAllowedClaimsPageSize(10)).toBe(true);
    expect(isAllowedClaimsPageSize(25)).toBe(false);
    expect(isAllowedClaimsPageSize(5)).toBe(false);
  });
});

describe('claims query pageSize canonicalization', () => {
  it('omits default pageSize from canonical URL', () => {
    const result = parseCanonicalClaimsQuery('');
    expect(result.filters.pageSize).toBeUndefined();
    expect(result.canonicalSearch).not.toContain('pageSize');
  });

  it('rejects legacy 25-row page size', () => {
    const result = parseCanonicalClaimsQuery('?pageSize=25');
    expect(result.isCanonical).toBe(false);
    expect(result.filters.pageSize).toBeUndefined();
    expect(result.canonicalSearch).not.toContain('pageSize=25');
  });

  it('preserves explicit sizes inside the supervisory window', () => {
    const result = parseCanonicalClaimsQuery('?pageSize=8');
    expect(result.isCanonical).toBe(true);
    expect(result.filters.pageSize).toBe(8);
    expect(result.canonicalSearch).toContain('pageSize=8');
  });
});
