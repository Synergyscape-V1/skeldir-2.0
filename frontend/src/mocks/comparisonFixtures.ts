import type { DateRangeValue, PlatformType } from "../types/channel";
import type {
  AvailableChannel,
  BudgetRecommendation,
  ComparisonChannelData,
  ComparisonScenario,
  ComparisonViewModel,
  WinnerDeclaration,
} from "../types/comparison";

const CHANNEL_ORDER = ["ch_google_ads", "ch_facebook_ads", "ch_tiktok_ads", "ch_pinterest_ads"] as const;
const DATE_END = "2024-11-30T00:00:00Z";

type MockSeed = {
  id: string;
  name: string;
  platform_type: PlatformType;
  performance: {
    revenue: number;
    spend: number;
    roas: number;
    conversions: number;
  };
  confidenceRange: {
    low: number;
    high: number;
    level: "high" | "medium" | "low";
    explanation: string;
  };
  wave: number;
};

const BASE_SEEDS: MockSeed[] = [
  {
    id: "ch_google_ads",
    name: "Google Ads",
    platform_type: "google_ads",
    performance: { revenue: 18620000, spend: 4520000, roas: 4.12, conversions: 247 },
    confidenceRange: {
      low: 3.85,
      high: 4.5,
      level: "high",
      explanation: "High sample stability with narrow posterior interval over the selected window.",
    },
    wave: 0.08,
  },
  {
    id: "ch_facebook_ads",
    name: "Meta Ads",
    platform_type: "facebook_ads",
    performance: { revenue: 13810000, spend: 3610000, roas: 3.65, conversions: 183 },
    confidenceRange: {
      low: 3.5,
      high: 3.8,
      level: "high",
      explanation: "Consistent attribution path depth produces a tight confidence interval.",
    },
    wave: 0.11,
  },
  {
    id: "ch_tiktok_ads",
    name: "TikTok Ads",
    platform_type: "tiktok_ads",
    performance: { revenue: 680000, spend: 320000, roas: 2.13, conversions: 62 },
    confidenceRange: {
      low: 1.8,
      high: 2.5,
      level: "medium",
      explanation: "Moderate signal quality with wider variance in post-click conversion lag.",
    },
    wave: 0.16,
  },
  {
    id: "ch_pinterest_ads",
    name: "Pinterest Ads",
    platform_type: "pinterest_ads",
    performance: { revenue: 2510000, spend: 1250000, roas: 1.85, conversions: 28 },
    confidenceRange: {
      low: 1.2,
      high: 2.6,
      level: "medium",
      explanation: "Sparse conversion density increases posterior uncertainty for this channel.",
    },
    wave: 0.2,
  },
];

const availableChannels: AvailableChannel[] = BASE_SEEDS.map((seed) => ({
  id: seed.id,
  name: seed.name,
  platform_type: seed.platform_type,
}));

function daysForRange(range: DateRangeValue): number {
  if (range === "last_7_days") return 7;
  if (range === "last_60_days") return 60;
  if (range === "last_90_days") return 90;
  return 30;
}

function rangeStart(range: DateRangeValue): string {
  const end = new Date(DATE_END);
  end.setUTCDate(end.getUTCDate() - (daysForRange(range) - 1));
  return end.toISOString().slice(0, 10);
}

function buildTrend(seed: MockSeed, days: number): ComparisonChannelData["trendData"] {
  const end = new Date(DATE_END);
  const dailyRevenue = seed.performance.revenue / days;
  const dailySpend = seed.performance.spend / days;

  return Array.from({ length: days }, (_, index) => {
    const pointDate = new Date(end);
    pointDate.setUTCDate(end.getUTCDate() - (days - 1 - index));
    const drift = Math.sin(index / 3.4) * seed.wave + Math.cos(index / 8) * 0.03;
    const revenue = Math.round(dailyRevenue * (1 + drift));
    const spend = Math.round(dailySpend * (1 + drift * 0.72));
    const roas = Number((seed.performance.roas * (1 + drift * 0.38)).toFixed(2));
    const rangeWidth =
      seed.confidenceRange.level === "high" ? 0.22 : seed.confidenceRange.level === "medium" ? 0.38 : 0.58;

    return {
      date: pointDate.toISOString().slice(0, 10),
      revenue,
      spend,
      roas,
      roasRangeLow: Number((roas - rangeWidth).toFixed(2)),
      roasRangeHigh: Number((roas + rangeWidth).toFixed(2)),
    };
  });
}

function materializeChannel(seed: MockSeed, dateRange: DateRangeValue): ComparisonChannelData {
  const days = daysForRange(dateRange);
  return {
    channel: {
      id: seed.id,
      name: seed.name,
      platform_type: seed.platform_type,
    },
    dateRange: {
      start: rangeStart(dateRange),
      end: DATE_END.slice(0, 10),
    },
    performance: seed.performance,
    confidenceRange: seed.confidenceRange,
    trendData: buildTrend(seed, days),
  };
}

function computeWinner(channelData: Record<string, ComparisonChannelData>): WinnerDeclaration | null {
  const loaded = Object.values(channelData);
  if (loaded.length < 2) return null;
  const sorted = [...loaded].sort((a, b) => b.performance.roas - a.performance.roas);
  const leader = sorted[0];
  const second = sorted[1];
  const rangesOverlap = leader.confidenceRange.low <= second.confidenceRange.high;
  if (rangesOverlap) return null;
  return {
    channelId: leader.channel.id,
    channelName: leader.channel.name,
    roas: leader.performance.roas,
    delta: leader.performance.roas - second.performance.roas,
  };
}

function computeBudgetRecommendation(
  channelData: Record<string, ComparisonChannelData>,
  winner: WinnerDeclaration | null
): BudgetRecommendation | null {
  const loaded = Object.values(channelData);
  if (loaded.length < 2 || !winner) return null;

  const hasGoogle = loaded.some((item) => item.channel.id === "ch_google_ads");
  const hasPinterest = loaded.some((item) => item.channel.id === "ch_pinterest_ads");
  if (hasGoogle && hasPinterest && winner.channelId === "ch_google_ads") {
    return {
      fromChannelId: "ch_pinterest_ads",
      fromChannelName: "Pinterest Ads",
      toChannelId: "ch_google_ads",
      toChannelName: "Google Ads",
      shiftAmount: 850000,
      expectedRevenueIncrease: 2100000,
      confidence: "medium",
    };
  }

  if (loaded.length !== 2) return null;
  const [lead, lag] = [...loaded].sort((a, b) => b.performance.roas - a.performance.roas);
  const ratio = (lead.performance.roas - lag.performance.roas) / lag.performance.roas;
  if (ratio < 0.15) return null;
  const shiftAmount = Math.round(lag.performance.spend * 0.2);
  const expectedRevenueIncrease = Math.round(shiftAmount * (lead.performance.roas - lag.performance.roas));
  return {
    fromChannelId: lag.channel.id,
    fromChannelName: lag.channel.name,
    toChannelId: lead.channel.id,
    toChannelName: lead.channel.name,
    shiftAmount,
    expectedRevenueIncrease,
    confidence: lead.confidenceRange.level,
  };
}

function pickChannelIds(scenario: ComparisonScenario): string[] {
  if (scenario === "empty") return [];
  if (scenario === "three_channels") return [...CHANNEL_ORDER.slice(0, 3)];
  if (scenario === "four_channels") return [...CHANNEL_ORDER];
  return [...CHANNEL_ORDER.slice(0, 3)];
}

export function buildComparisonViewModel(
  scenario: ComparisonScenario,
  dateRange: DateRangeValue = "last_30_days",
  selectedChannels: string[] = pickChannelIds(scenario)
): ComparisonViewModel {
  const selectedChannelIds = selectedChannels.filter((id) => CHANNEL_ORDER.includes(id as (typeof CHANNEL_ORDER)[number])).slice(0, 4);
  const channelData: Record<string, ComparisonChannelData> = {};
  const loading: Record<string, boolean> = {};
  const errors: ComparisonViewModel["errors"] = {};

  if (scenario === "loading") {
    selectedChannelIds.forEach((id) => {
      loading[id] = true;
      errors[id] = null;
    });
    return {
      selectedChannelIds,
      channelData,
      loading,
      errors,
      availableChannels,
      dateRange,
      winner: null,
      budgetRecommendation: null,
    };
  }

  selectedChannelIds.forEach((id) => {
    const seed = BASE_SEEDS.find((item) => item.id === id);
    if (!seed) return;
    channelData[id] = materializeChannel(seed, dateRange);
    loading[id] = false;
    errors[id] = null;
  });

  if (scenario === "error" && selectedChannelIds.length > 0) {
    const errorId = selectedChannelIds[selectedChannelIds.length - 1];
    delete channelData[errorId];
    errors[errorId] = {
      message: "Failed to load channel detail",
      correlationId: "corr-compare-500",
    };
  }

  if (scenario === "no_winner" && selectedChannelIds.length >= 2) {
    const first = selectedChannelIds[0];
    const second = selectedChannelIds[1];
    if (channelData[first] && channelData[second]) {
      channelData[first] = {
        ...channelData[first],
        confidenceRange: { ...channelData[first].confidenceRange, low: 3.2, high: 4.15 },
      };
      channelData[second] = {
        ...channelData[second],
        confidenceRange: { ...channelData[second].confidenceRange, low: 3.0, high: 3.8 },
      };
    }
  }

  const winner = computeWinner(channelData);
  const budgetRecommendation = computeBudgetRecommendation(channelData, winner);
  return {
    selectedChannelIds,
    channelData,
    loading,
    errors,
    availableChannels,
    dateRange,
    winner,
    budgetRecommendation,
  };
}

export const STORYBOOK_MOCK_CHANNELS: ComparisonChannelData[] = BASE_SEEDS.map((seed) =>
  materializeChannel(seed, "last_30_days")
);
