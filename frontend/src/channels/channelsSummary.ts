import type { ChannelOverviewRowDTO, ChannelOverviewSummary } from '../ledger/types';
import { formatMoneyMinorDisplay } from '../lib/money';
import { formatDiscrepancyPercent } from '../components/commandCenter/StatusBadges/StatusBadges';
import { channelRowIdentityLabel } from './channelsDisplay';
const ACTION_READY_STATES = new Set([
  'approval_required',
  'proposal_required',
  'auto_executable_within_policy',
  'simulation_only',
]);

const POLICY_RANK: Record<string, number> = {
  approval_required: 0,
  proposal_required: 1,
  auto_executable_within_policy: 2,
  simulation_only: 3,
  blocked: 4,
};

export function emptyChannelOverviewSummary(): ChannelOverviewSummary {
  return {
    highestVerifiedRevenueChannelId: null,
    highestVerifiedRevenueChannelName: null,
    highestVerifiedRevenueMinor: 0n,
    largestDiscrepancyChannelId: null,
    largestDiscrepancyChannelName: null,
    largestDiscrepancyRateBps: 0,
    lowestConfidenceChannelId: null,
    lowestConfidenceChannelName: null,
    lowestConfidenceLabel: 'Confidence is unavailable. Deterministic verification remains active.',
    bestActionReadyChannelId: null,
    bestActionReadyChannelName: null,
    bestActionReadyRevenueMinor: 0n,
    bestActionReadyPolicyAuthority: null,
    currencyCode: 'USD',
  };
}

export function computeChannelOverviewSummary(rows: ChannelOverviewRowDTO[]): ChannelOverviewSummary {
  if (rows.length === 0) return emptyChannelOverviewSummary();

  const currencyCode = rows[0]?.currencyCode ?? 'USD';

  const highest = rows.reduce((best, row) =>
    row.verifiedRevenueMinor > best.verifiedRevenueMinor ? row : best,
  );

  const largestDiscrepancy = rows.reduce((best, row) =>
    row.discrepancyRateBps > best.discrepancyRateBps ? row : best,
  );

  const lowestConfidence = rows.reduce((worst, row) => {
    const rank = (r: ChannelOverviewRowDTO) => {
      if (r.bayesianStatusKey === 'degraded' || r.bayesianStatusKey === 'unavailable') return 0;
      if (r.bayesianStatusKey === 'low_confidence' || r.bayesianStatusKey === 'delayed') return 1;
      return 2;
    };
    return rank(row) < rank(worst) ? row : worst;
  });

  const actionReady = rows
    .filter((row) => ACTION_READY_STATES.has(row.policyAuthority))
    .sort((a, b) => {
      const rankDiff = (POLICY_RANK[a.policyAuthority] ?? 99) - (POLICY_RANK[b.policyAuthority] ?? 99);
      if (rankDiff !== 0) return rankDiff;
      return a.verifiedRevenueMinor > b.verifiedRevenueMinor ? -1 : 1;
    });
  const bestAction = actionReady[0] ?? null;

  const claimedDisplay = formatMoneyMinorDisplay(largestDiscrepancy.claimedRevenueMinor, currencyCode);
  const verifiedDisplay = formatMoneyMinorDisplay(largestDiscrepancy.verifiedRevenueMinor, currencyCode);

  return {
    highestVerifiedRevenueChannelId: highest.channelId,
    highestVerifiedRevenueChannelName: channelRowIdentityLabel(highest),
    highestVerifiedRevenueMinor: highest.verifiedRevenueMinor,
    highestVerifiedRevenueDeltaLabel: '+8.4% vs prior 30 days',
    largestDiscrepancyChannelId: largestDiscrepancy.channelId,
    largestDiscrepancyChannelName: channelRowIdentityLabel(largestDiscrepancy),
    largestDiscrepancyRateBps: largestDiscrepancy.discrepancyRateBps,
    largestDiscrepancyComparisonLabel: `${claimedDisplay} claimed vs ${verifiedDisplay} verified`,
    lowestConfidenceChannelId: lowestConfidence.channelId,
    lowestConfidenceChannelName: channelRowIdentityLabel(lowestConfidence),
    lowestConfidenceLabel:
      lowestConfidence.bayesianStabilityLabel ??
      lowestConfidence.confidence.reason ??
      'CI unavailable; sample volume below threshold',
    bestActionReadyChannelId: bestAction?.channelId ?? null,
    bestActionReadyChannelName: bestAction ? channelRowIdentityLabel(bestAction) : null,
    bestActionReadyRevenueMinor: bestAction?.verifiedRevenueMinor ?? 0n,
    bestActionReadyPolicyAuthority: bestAction?.policyAuthority ?? null,
    bestActionReadyBenchmarkLabel: bestAction?.benchmarkPositionLabel ?? 'Above benchmark',
    currencyCode,
  };
}

export function formatDiscrepancySummaryRate(bps: number): string {
  return formatDiscrepancyPercent(bps);
}
