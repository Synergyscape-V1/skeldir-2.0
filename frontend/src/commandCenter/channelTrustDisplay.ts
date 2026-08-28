import type { PolicyAuthorityState } from '../lib/types';
import type { BenchmarkEvidenceClass } from '../ledger/types';
import { CAMPAIGN_CLASS_LABELS, CLAIM_SOURCE_LABELS, COMMERCE_RAIL_LABELS } from '../claims/claimsFilterConfig';
import { formatBpsAsPercentOneDecimal } from '../lib/money';
import type { ChannelTrustGroupBy, ChannelTrustRow } from './types';

const POLICY_SORT_ORDER: Record<PolicyAuthorityState, number> = {
  approval_required: 0,
  blocked: 1,
  proposal_required: 2,
  simulation_only: 3,
  auto_executable_within_policy: 4,
};

export const CHANNEL_TRUST_GROUP_BY_OPTIONS: Array<{ id: ChannelTrustGroupBy; label: string }> = [
  { id: 'platform', label: 'Group by platform' },
  { id: 'campaign_class', label: 'Group by campaign class' },
  { id: 'commerce_rail', label: 'Group by commerce rail' },
];

export function channelTrustAxisHeader(groupBy: ChannelTrustGroupBy): string {
  switch (groupBy) {
    case 'platform':
      return 'Claim source (platform)';
    case 'campaign_class':
      return 'Campaign class';
    case 'commerce_rail':
      return 'Commerce rail';
    default:
      return 'Claim source (platform)';
  }
}

export type DiscrepancyRateTier = 'green' | 'amber' | 'red' | 'unavailable';

export function discrepancyRateTier(bps: number | null | undefined): DiscrepancyRateTier {
  if (bps === null || bps === undefined) return 'unavailable';
  if (bps < 200) return 'green';
  if (bps <= 1000) return 'amber';
  return 'red';
}

export function formatChannelDiscrepancyRate(bps: number | null | undefined): string {
  if (bps === null || bps === undefined) return 'N/A';
  return formatBpsAsPercentOneDecimal(bps);
}

export function sortChannelTrustRows(rows: ChannelTrustRow[]): ChannelTrustRow[] {
  return [...rows].sort((a, b) => {
    const policyDelta =
      POLICY_SORT_ORDER[a.policyAuthority] - POLICY_SORT_ORDER[b.policyAuthority];
    if (policyDelta !== 0) return policyDelta;

    const aBps = a.discrepancyRateBps ?? -1;
    const bBps = b.discrepancyRateBps ?? -1;
    if (aBps !== bBps) return bBps - aBps;

    if (a.verifiedRevenueMinor !== b.verifiedRevenueMinor) {
      return a.verifiedRevenueMinor > b.verifiedRevenueMinor ? -1 : 1;
    }

    return a.rowId.localeCompare(b.rowId);
  });
}

export function resolveAxisLabel(row: ChannelTrustRow, groupBy: ChannelTrustGroupBy): string {
  switch (groupBy) {
    case 'platform':
      return CLAIM_SOURCE_LABELS[row.claimSource] ?? row.axisLabel;
    case 'campaign_class':
      return CAMPAIGN_CLASS_LABELS[row.campaignClass] ?? row.axisLabel;
    case 'commerce_rail':
      return COMMERCE_RAIL_LABELS[row.commerceRail] ?? row.axisLabel;
    default:
      return row.axisLabel;
  }
}

export function showPlatformLogo(groupBy: ChannelTrustGroupBy): boolean {
  return groupBy === 'platform';
}

export function verifiedRevenueMinorTitle(minor: bigint, currencyCode: string): string {
  return `${minor.toString()} minor units (${currencyCode})`;
}

export function benchmarkCellTitle(
  evidenceClass: BenchmarkEvidenceClass,
  reason?: string,
): string | undefined {
  if (evidenceClass === 'unavailable') {
    return reason ?? 'Insufficient cross-tenant signal. Exact bucket suppressed for privacy.';
  }
  return undefined;
}
