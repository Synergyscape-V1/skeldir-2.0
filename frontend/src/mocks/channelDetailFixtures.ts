import type {
  ChannelDetailData,
  ChannelDetailResponse,
  ChannelDetailScenario,
  DateRangeValue,
  PlatformType,
} from "../types/channel";

export type ChannelDatasetVariant = "high" | "mixed" | "low";

function buildTrend(days: number, revenueBase: number, spendBase: number, roasBase: number) {
  const now = new Date("2024-11-30T00:00:00Z");
  const out: ChannelDetailResponse["trend"] = [];
  for (let i = days - 1; i >= 0; i -= 1) {
    const d = new Date(now);
    d.setUTCDate(now.getUTCDate() - i);
    const wave = Math.sin(i / 4) * 0.08;
    const revenue = Math.round(revenueBase * (1 + wave));
    const spend = Math.round(spendBase * (1 + wave * 0.7));
    const roas = Number((roasBase * (1 + wave * 0.6)).toFixed(2));
    const bandNoise = Math.sin(i / 3) * 0.05;
    out.push({
      date: d.toISOString().slice(0, 10),
      revenue,
      spend,
      roas,
      roas_range_low: Number((roas - 0.25).toFixed(2)),
      roas_range_high: Number((roas + 0.25).toFixed(2)),
      revenue_low: Math.round(revenue * (0.78 + bandNoise)),
      revenue_high: Math.round(revenue * (1.22 + bandNoise)),
    });
  }
  return out;
}

const channelCatalog: Record<string, { name: string; platform_type: PlatformType }> = {
  ch_google_ads: { name: "Google Ads", platform_type: "google_ads" },
  ch_facebook_ads: { name: "Facebook Ads", platform_type: "facebook_ads" },
  ch_meta_ads: { name: "Meta Ads", platform_type: "facebook_ads" },
  ch_tiktok_ads: { name: "TikTok Ads", platform_type: "tiktok_ads" },
  ch_pinterest_ads: { name: "Pinterest Ads", platform_type: "pinterest_ads" },
};

function daysFromRange(range: DateRangeValue): number {
  if (range === "last_7_days") return 7;
  if (range === "last_60_days") return 60;
  if (range === "last_90_days") return 90;
  return 30;
}

function sampleResponse(
  channelId: string,
  dateRange: DateRangeValue,
  dataset: ChannelDatasetVariant
): ChannelDetailResponse {
  const channel = channelCatalog[channelId] ?? channelCatalog.ch_google_ads;
  const days = daysFromRange(dateRange);

  const baseByDataset = {
    high: {
      revenue: 6200000, spend: 1460000, roas: 4.25, discrepancyPercent: -3.2, level: "high" as const,
      revenueChange: 15, roasChange: 0.22, spendChange: -3, conversionsChange: 12,
      confidenceLevels: { revenue: "high" as const, roas: "high" as const, spend: "high" as const, conversions: "high" as const },
    },
    mixed: {
      revenue: 4820000, spend: 1245000, roas: 3.87, discrepancyPercent: -7.9, level: "medium" as const,
      revenueChange: 8, roasChange: 0.10, spendChange: 3, conversionsChange: 5,
      confidenceLevels: { revenue: "high" as const, roas: "high" as const, spend: "medium" as const, conversions: "high" as const },
    },
    low: {
      revenue: 3300000, spend: 1390000, roas: 2.37, discrepancyPercent: -18.4, level: "low" as const,
      revenueChange: -2, roasChange: -0.08, spendChange: 15, conversionsChange: -3,
      confidenceLevels: { revenue: "low" as const, roas: "low" as const, spend: "medium" as const, conversions: "low" as const },
    },
  }[dataset];

  const platformClaimedRevenue = Math.round(baseByDataset.revenue * (1 + Math.abs(baseByDataset.discrepancyPercent) / 100));
  const discrepancy = baseByDataset.revenue - platformClaimedRevenue;

  return {
    channel: {
      id: channelId,
      name: channel.name,
      platform_type: channel.platform_type,
    },
    date_range: {
      start: new Date(new Date("2024-11-30T00:00:00Z").setUTCDate(30 - days + 1)).toISOString().slice(0, 10),
      end: "2024-11-30",
    },
    performance: {
      revenue: baseByDataset.revenue,
      spend: baseByDataset.spend,
      roas: baseByDataset.roas,
      conversions: Math.round(baseByDataset.revenue / 19500),
      revenue_change: baseByDataset.revenueChange,
      roas_change: baseByDataset.roasChange,
      spend_change: baseByDataset.spendChange,
      conversions_change: baseByDataset.conversionsChange,
    },
    verification: {
      platform_claimed_revenue: platformClaimedRevenue,
      verified_revenue: baseByDataset.revenue,
      discrepancy,
      discrepancy_percent: baseByDataset.discrepancyPercent,
      matched_transaction_count: Math.round(baseByDataset.revenue / 19500),
    },
    confidence: {
      roas_range_low: Number((baseByDataset.roas - (dataset === "high" ? 0.18 : dataset === "mixed" ? 0.35 : 0.7)).toFixed(2)),
      roas_range_high: Number((baseByDataset.roas + (dataset === "high" ? 0.22 : dataset === "mixed" ? 0.38 : 0.78)).toFixed(2)),
      confidence_level: baseByDataset.level,
      explanation:
        dataset === "high"
          ? `Your ${channel.name} confidence is narrow because the last ${days} days have stable volume and consistent conversion behavior.`
          : dataset === "mixed"
            ? `Your ${channel.name} confidence is moderate because performance is stable overall, but weekly volatility increases uncertainty.`
            : `Your ${channel.name} confidence is wide because sparse and volatile conversion signals require a broader Bayesian interval.`,
    },
    confidence_levels: baseByDataset.confidenceLevels,
    trend: buildTrend(days, Math.round(baseByDataset.revenue / days), Math.round(baseByDataset.spend / days), baseByDataset.roas),
  };
}

export function transformChannelDetailResponse(raw: ChannelDetailResponse): ChannelDetailData {
  return {
    channel: {
      id: raw.channel.id,
      name: raw.channel.name,
      platform_type: raw.channel.platform_type,
    },
    dateRange: {
      start: raw.date_range.start,
      end: raw.date_range.end,
    },
    performance: {
      revenue: raw.performance.revenue,
      spend: raw.performance.spend,
      roas: raw.performance.roas,
      conversions: raw.performance.conversions,
      revenueChange: raw.performance.revenue_change,
      roasChange: raw.performance.roas_change,
      spendChange: raw.performance.spend_change,
      conversionsChange: raw.performance.conversions_change,
    },
    verification: {
      platformClaimed: raw.verification.platform_claimed_revenue,
      verified: raw.verification.verified_revenue,
      discrepancy: raw.verification.discrepancy,
      discrepancyPercent: raw.verification.discrepancy_percent,
      transactionCount: raw.verification.matched_transaction_count,
    },
    confidenceRange: {
      low: raw.confidence.roas_range_low,
      high: raw.confidence.roas_range_high,
      level: raw.confidence.confidence_level,
      explanation: raw.confidence.explanation,
    },
    confidenceLevels: raw.confidence_levels,
    trendData: raw.trend.map((t) => ({
      date: t.date,
      revenue: t.revenue,
      spend: t.spend,
      roas: t.roas,
      roasRangeLow: t.roas_range_low,
      roasRangeHigh: t.roas_range_high,
      revenueLow: t.revenue_low,
      revenueHigh: t.revenue_high,
    })),
  };
}

export interface ChannelHarnessState {
  scenario: ChannelDetailScenario;
  data: ChannelDetailData | null;
  loading: boolean;
  error: { message: string; correlationId: string | null } | null;
  notFound: boolean;
  updating: boolean;
}

export function getChannelDetailHarnessState(
  scenario: ChannelDetailScenario,
  channelId: string,
  dateRange: DateRangeValue,
  dataset: ChannelDatasetVariant
): ChannelHarnessState {
  const data = transformChannelDetailResponse(sampleResponse(channelId, dateRange, dataset));
  if (scenario === "loading") {
    return { scenario, data: null, loading: true, error: null, notFound: false, updating: false };
  }
  if (scenario === "error") {
    return {
      scenario,
      data: null,
      loading: false,
      error: { message: "Failed to load channel detail", correlationId: "corr-channel-001" },
      notFound: false,
      updating: false,
    };
  }
  if (scenario === "not_found") {
    return { scenario, data: null, loading: false, error: null, notFound: true, updating: false };
  }
  if (scenario === "updating") {
    return { scenario, data, loading: false, error: null, notFound: false, updating: true };
  }
  return { scenario: "steady", data, loading: false, error: null, notFound: false, updating: false };
}
