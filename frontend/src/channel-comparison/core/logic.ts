import { formatCurrency, formatRevenueDelta, formatROAS, formatROASDelta } from "../../lib/formatters";
import type {
  BudgetRecommendation,
  ComparisonChannelData,
  ChannelComparisonDerivedMetric,
  WinnerDeclaration,
} from "../../types/comparison";

function sortByMetric<T extends ComparisonChannelData>(
  channels: T[],
  selector: (channel: T) => number
): T[] {
  return [...channels].sort((a, b) => selector(b) - selector(a));
}

export function computeWinner(channels: ComparisonChannelData[]): WinnerDeclaration | null {
  if (channels.length < 2) return null;
  const sorted = sortByMetric(channels, (channel) => channel.performance.roas);
  const leader = sorted[0];
  const runnerUp = sorted[1];
  const rangesOverlap = leader.confidenceRange.low <= runnerUp.confidenceRange.high;
  if (rangesOverlap) return null;
  return {
    channelId: leader.channel.id,
    channelName: leader.channel.name,
    roas: leader.performance.roas,
    delta: leader.performance.roas - runnerUp.performance.roas,
  };
}

export function computeBudgetRecommendation(
  channels: ComparisonChannelData[],
  winner: WinnerDeclaration | null
): BudgetRecommendation | null {
  if (channels.length < 2 || winner === null) return null;

  const ordered = sortByMetric(channels, (channel) => channel.performance.roas);
  const leader = ordered[0];
  const loser = ordered[ordered.length - 1];
  const ratio = (leader.performance.roas - loser.performance.roas) / loser.performance.roas;
  if (ratio < 0.15) return null;

  const shiftAmount = Math.round(loser.performance.spend * 0.2);
  const expectedRevenueIncrease = Math.round(shiftAmount * (leader.performance.roas - loser.performance.roas));
  return {
    fromChannelId: loser.channel.id,
    fromChannelName: loser.channel.name,
    toChannelId: leader.channel.id,
    toChannelName: leader.channel.name,
    shiftAmount,
    expectedRevenueIncrease,
    confidence: leader.confidenceRange.level,
  };
}

export function buildDerivedMetrics(channels: ComparisonChannelData[]): Record<string, ChannelComparisonDerivedMetric> {
  const bestByRevenue = sortByMetric(channels, (channel) => channel.performance.revenue)[0];
  const secondByRevenue = sortByMetric(channels, (channel) => channel.performance.revenue)[1] ?? bestByRevenue;
  const bestByRoas = sortByMetric(channels, (channel) => channel.performance.roas)[0];
  const secondByRoas = sortByMetric(channels, (channel) => channel.performance.roas)[1] ?? bestByRoas;
  const bestByConversions = sortByMetric(channels, (channel) => channel.performance.conversions)[0];
  const secondByConversions = sortByMetric(channels, (channel) => channel.performance.conversions)[1] ?? bestByConversions;

  const response: Record<string, ChannelComparisonDerivedMetric> = {};

  channels.forEach((channel) => {
    const revenueDeltaBase =
      channel.channel.id === bestByRevenue.channel.id
        ? channel.performance.revenue - secondByRevenue.performance.revenue
        : channel.performance.revenue - bestByRevenue.performance.revenue;
    const roasDeltaBase =
      channel.channel.id === bestByRoas.channel.id
        ? channel.performance.roas - secondByRoas.performance.roas
        : channel.performance.roas - bestByRoas.performance.roas;
    const conversionsDeltaBase =
      channel.channel.id === bestByConversions.channel.id
        ? channel.performance.conversions - secondByConversions.performance.conversions
        : channel.performance.conversions - bestByConversions.performance.conversions;

    response[channel.channel.id] = {
      channelId: channel.channel.id,
      isBestByRoas: channel.channel.id === bestByRoas.channel.id,
      isBestByRevenue: channel.channel.id === bestByRevenue.channel.id,
      revenueDeltaLabel:
        channels.length >= 2
          ? `${formatRevenueDelta(revenueDeltaBase)} vs ${
              channel.channel.id === bestByRevenue.channel.id ? secondByRevenue.channel.name : bestByRevenue.channel.name
            }`
          : null,
      roasDeltaLabel:
        channels.length >= 2
          ? `${formatROASDelta(roasDeltaBase)} vs ${
              channel.channel.id === bestByRoas.channel.id ? secondByRoas.channel.name : bestByRoas.channel.name
            }`
          : null,
      conversionDeltaLabel:
        channels.length >= 2
          ? `${conversionsDeltaBase >= 0 ? "+" : "-"}${Math.abs(conversionsDeltaBase)} conversions vs ${
              channel.channel.id === bestByConversions.channel.id ? secondByConversions.channel.name : bestByConversions.channel.name
            }`
          : null,
    };
  });

  return response;
}

export function confidenceTierDescription(level: "high" | "medium" | "low"): string {
  if (level === "high") return "High Confidence";
  if (level === "medium") return "Medium Confidence";
  return "Low Confidence";
}

export function winnerHeadline(channels: ComparisonChannelData[], winner: WinnerDeclaration | null): string {
  if (winner === null) return "No statistically reliable winner yet";
  const runnerUp = sortByMetric(channels, (channel) => channel.performance.roas).find((channel) => channel.channel.id !== winner.channelId);
  if (!runnerUp) return `${winner.channelName} leads on ROAS`;
  return `${winner.channelName} (${formatROAS(winner.roas)}) leads ${runnerUp.channel.name} by ${formatROAS(winner.delta)} ROAS`;
}

export function budgetRecommendationText(recommendation: BudgetRecommendation): string {
  return `Shift ${formatCurrency(recommendation.shiftAmount)} from ${recommendation.fromChannelName} to ${recommendation.toChannelName}`;
}
