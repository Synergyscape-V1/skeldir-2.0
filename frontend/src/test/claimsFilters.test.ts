import { describe, expect, it } from 'vitest';
import {
  buildActiveClaimsFilterChips,
  clearClaimsFilterChip,
  hasActiveClaimsFilters,
} from '../claims/claimsFilterConfig';
import { presetToDateRange, resolveDateRangePreset } from '../claims/claimsDateRange';

describe('claimsDateRange', () => {
  it('maps last_30_days preset to canonical ISO date bounds', () => {
    const range = presetToDateRange('last_30_days');
    expect(range.dateFrom).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(range.dateTo).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(resolveDateRangePreset(range.dateFrom, range.dateTo)).toBe('last_30_days');
  });

  it('clears dates for all preset', () => {
    expect(presetToDateRange('all')).toEqual({ dateFrom: undefined, dateTo: undefined });
  });
});

describe('claimsFilterConfig', () => {
  it('builds chips for active dimensions', () => {
    const chips = buildActiveClaimsFilterChips({
      claimSource: 'meta_ads',
      campaignClass: 'paid_search',
      commerceRail: 'organic',
      discrepancyClass: 'flagged',
      search: 'claim_0001',
    });
    expect(chips.map((c) => c.label)).toEqual([
      'Meta Ads',
      'Paid Search',
      'Organic',
      'Flagged',
      'Search: claim_0001',
    ]);
  });

  it('clears individual chip keys', () => {
    const next = clearClaimsFilterChip(
      { claimSource: 'meta_ads', verificationStatus: 'partial', offset: 25 },
      'claimSource',
    );
    expect(next.claimSource).toBeUndefined();
    expect(next.verificationStatus).toBe('partial');
    expect(next.offset).toBe(0);
  });

  it('detects active filters without sort keys', () => {
    expect(hasActiveClaimsFilters({ sortKey: 'lastUpdated' })).toBe(false);
    expect(hasActiveClaimsFilters({ policyAuthority: 'blocked' })).toBe(true);
  });
});
