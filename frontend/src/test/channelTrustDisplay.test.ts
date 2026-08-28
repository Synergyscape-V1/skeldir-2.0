import { describe, expect, it } from 'vitest';
import { sortChannelTrustRows, discrepancyRateTier, formatChannelDiscrepancyRate } from '../commandCenter/channelTrustDisplay';
import type { ChannelTrustRow } from '../commandCenter/types';

function row(partial: Partial<ChannelTrustRow> & Pick<ChannelTrustRow, 'rowId' | 'policyAuthority'>): ChannelTrustRow {
  return {
    channelId: partial.rowId,
    axisLabel: partial.axisLabel ?? partial.rowId,
    claimSource: 'google_ads',
    campaignClass: 'paid_search',
    commerceRail: 'organic',
    verifiedRevenueMinor: 1_000_000n,
    currencyCode: 'USD',
    discrepancyRateBps: 500,
    modelAgreementTier: 'high',
    benchmarkValue: '4.2% CVR',
    benchmarkEvidenceClass: 'live_empirical',
    ...partial,
  };
}

describe('channelTrustDisplay', () => {
  it('sorts by policy authority, then discrepancy, then revenue', () => {
    const sorted = sortChannelTrustRows([
      row({ rowId: 'sim', policyAuthority: 'simulation_only', discrepancyRateBps: 900, verifiedRevenueMinor: 9_000n }),
      row({ rowId: 'blocked', policyAuthority: 'blocked', discrepancyRateBps: 200, verifiedRevenueMinor: 12_000n }),
      row({ rowId: 'approval', policyAuthority: 'approval_required', discrepancyRateBps: 100, verifiedRevenueMinor: 1_000n }),
      row({ rowId: 'blocked-high', policyAuthority: 'blocked', discrepancyRateBps: 800, verifiedRevenueMinor: 8_000n }),
    ]);
    expect(sorted.map((r) => r.rowId)).toEqual(['approval', 'blocked-high', 'blocked', 'sim']);
  });

  it('color-codes discrepancy tiers and uses N/A for null bps', () => {
    expect(discrepancyRateTier(150)).toBe('green');
    expect(discrepancyRateTier(500)).toBe('amber');
    expect(discrepancyRateTier(1100)).toBe('red');
    expect(formatChannelDiscrepancyRate(null)).toBe('N/A');
  });
});
