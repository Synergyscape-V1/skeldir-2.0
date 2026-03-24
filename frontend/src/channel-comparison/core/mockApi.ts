import type { DateRangeValue, PlatformType } from "../../types/channel";
import type { AvailableChannel, ComparisonChannelData, ComparisonScenario } from "../../types/comparison";
import { DEFAULT_CHANNEL_IDS } from "./constants";

const FIXED_END_DATE = "2024-11-30";

type ChannelSeed = {
  id: string;
  name: string;
  platformType: PlatformType;
  performance: {
    revenue: number;
    spend: number;
    roas: number;
    conversions: number;
  };
  confidence: {
    low: number;
    high: number;
    level: "high" | "medium" | "low";
    explanation: string;
  };
  wave: number;
};

const CHANNEL_SEEDS: ChannelSeed[] = [
  {
    id: "ch_google_ads",
    name: "Google Ads",
    platformType: "google_ads",
    performance: { revenue: 18620000, spend: 4520000, roas: 4.12, conversions: 247 },
    confidence: {
      low: 3.85,
      high: 4.5,
      level: "high",
      explanation: "High sample stability with tight posterior interval.",
    },
    wave: 0.07,
  },
  {
    id: "ch_facebook_ads",
    name: "Meta Ads",
    platformType: "facebook_ads",
    performance: { revenue: 13810000, spend: 3810000, roas: 3.65, conversions: 183 },
    confidence: {
      low: 3.5,
      high: 3.8,
      level: "high",
      explanation: "Consistent conversion path and low variance.",
    },
    wave: 0.1,
  },
  {
    id: "ch_pinterest_ads",
    name: "Pinterest Ads",
    platformType: "pinterest_ads",
    performance: { revenue: 2510000, spend: 1250000, roas: 1.85, conversions: 28 },
    confidence: {
      low: 1.2,
      high: 2.8,
      level: "medium",
      explanation: "Sparse conversion volume creates wider uncertainty.",
    },
    wave: 0.18,
  },
  {
    id: "ch_tiktok_ads",
    name: "TikTok Ads",
    platformType: "tiktok_ads",
    performance: { revenue: 680000, spend: 320000, roas: 2.13, conversions: 62 },
    confidence: {
      low: 1.8,
      high: 2.5,
      level: "medium",
      explanation: "Moderate confidence with event timing variability.",
    },
    wave: 0.15,
  },
];

function daysForRange(range: DateRangeValue): number {
  if (range === "last_7_days") return 7;
  if (range === "last_60_days") return 60;
  if (range === "last_90_days") return 90;
  return 30;
}

function startDateForRange(range: DateRangeValue): string {
  const endDate = new Date(`${FIXED_END_DATE}T00:00:00Z`);
  endDate.setUTCDate(endDate.getUTCDate() - (daysForRange(range) - 1));
  return endDate.toISOString().slice(0, 10);
}

function buildTrendData(seed: ChannelSeed, range: DateRangeValue): ComparisonChannelData["trendData"] {
  const days = daysForRange(range);
  const end = new Date(`${FIXED_END_DATE}T00:00:00Z`);
  const dailyRevenue = seed.performance.revenue / days;
  const dailySpend = seed.performance.spend / days;

  return Array.from({ length: days }, (_, index) => {
    const date = new Date(end);
    date.setUTCDate(end.getUTCDate() - (days - 1 - index));
    const drift = Math.sin(index / 3.2) * seed.wave + Math.cos(index / 7.4) * 0.03;
    const revenue = Math.round(dailyRevenue * (1 + drift));
    const spend = Math.round(dailySpend * (1 + drift * 0.7));
    const roas = Number((seed.performance.roas * (1 + drift * 0.28)).toFixed(2));
    const width = seed.confidence.level === "high" ? 0.22 : seed.confidence.level === "medium" ? 0.36 : 0.54;
    return {
      date: date.toISOString().slice(0, 10),
      revenue,
      spend,
      roas,
      roasRangeLow: Number((roas - width).toFixed(2)),
      roasRangeHigh: Number((roas + width).toFixed(2)),
    };
  });
}

function toComparisonData(seed: ChannelSeed, range: DateRangeValue): ComparisonChannelData {
  return {
    channel: {
      id: seed.id,
      name: seed.name,
      platform_type: seed.platformType,
    },
    dateRange: {
      start: startDateForRange(range),
      end: FIXED_END_DATE,
    },
    performance: seed.performance,
    confidenceRange: {
      low: seed.confidence.low,
      high: seed.confidence.high,
      level: seed.confidence.level,
      explanation: seed.confidence.explanation,
    },
    trendData: buildTrendData(seed, range),
  };
}

export function defaultSelectedIds(scenario: ComparisonScenario): string[] {
  if (scenario === "empty") return [];
  if (scenario === "four_channels") return CHANNEL_SEEDS.map((seed) => seed.id);
  return [...DEFAULT_CHANNEL_IDS];
}

export async function fetchAvailableChannelsMock(shouldFail = false): Promise<AvailableChannel[]> {
  await new Promise((resolve) => setTimeout(resolve, 120));
  if (shouldFail) {
    throw new Error("Could not load channel list.");
  }
  return CHANNEL_SEEDS.map((seed) => ({
    id: seed.id,
    name: seed.name,
    platform_type: seed.platformType,
  }));
}

export async function fetchChannelDetailMock(
  channelId: string,
  dateRange: DateRangeValue,
  options?: { shouldFail?: boolean; noWinnerMode?: boolean }
): Promise<ComparisonChannelData> {
  await new Promise((resolve) => setTimeout(resolve, 120));
  if (options?.shouldFail) {
    throw new Error("Failed to load channel detail");
  }

  const seed = CHANNEL_SEEDS.find((item) => item.id === channelId);
  if (!seed) {
    throw new Error(`Unknown channel: ${channelId}`);
  }

  const data = toComparisonData(seed, dateRange);
  if (options?.noWinnerMode && (channelId === "ch_google_ads" || channelId === "ch_facebook_ads")) {
    if (channelId === "ch_google_ads") {
      return {
        ...data,
        confidenceRange: {
          ...data.confidenceRange,
          low: 3.2,
          high: 4.15,
        },
      };
    }
    return {
      ...data,
      confidenceRange: {
        ...data.confidenceRange,
        low: 3.0,
        high: 3.95,
      },
    };
  }

  return data;
}
