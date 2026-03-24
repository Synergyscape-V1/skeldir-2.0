import type { ConfidenceLevel } from "./dashboard";

export type PlatformType =
  | "google_ads"
  | "facebook_ads"
  | "tiktok_ads"
  | "pinterest_ads";

export type DateRangeValue =
  | "last_7_days"
  | "last_30_days"
  | "last_60_days"
  | "last_90_days"
  | "custom";

export interface ChannelDetailData {
  channel: {
    id: string;
    name: string;
    platform_type: PlatformType;
  };
  dateRange: {
    start: string;
    end: string;
  };
  performance: {
    revenue: number;
    spend: number;
    roas: number;
    conversions: number;
    revenueChange: number;
    roasChange: number;
    spendChange: number;
    conversionsChange: number;
  };
  verification: {
    platformClaimed: number;
    verified: number;
    discrepancy: number;
    discrepancyPercent: number;
    transactionCount: number;
  };
  confidenceRange: {
    low: number;
    high: number;
    level: ConfidenceLevel;
    explanation: string;
  };
  confidenceLevels: {
    revenue: ConfidenceLevel;
    roas: ConfidenceLevel;
    spend: ConfidenceLevel;
    conversions: ConfidenceLevel;
  };
  trendData: Array<{
    date: string;
    revenue: number;
    spend: number;
    roas: number;
    roasRangeLow: number;
    roasRangeHigh: number;
    revenueLow: number;
    revenueHigh: number;
  }>;
}

export interface ChannelDetailState {
  data: ChannelDetailData | null;
  loading: boolean;
  error: {
    message: string;
    correlationId: string | null;
  } | null;
}

export interface ChannelDetailResponse {
  channel: {
    id: string;
    name: string;
    platform_type: PlatformType;
  };
  date_range: {
    start: string;
    end: string;
  };
  performance: {
    revenue: number;
    spend: number;
    roas: number;
    conversions: number;
    revenue_change: number;
    roas_change: number;
    spend_change: number;
    conversions_change: number;
  };
  verification: {
    platform_claimed_revenue: number;
    verified_revenue: number;
    discrepancy: number;
    discrepancy_percent: number;
    matched_transaction_count: number;
  };
  confidence: {
    roas_range_low: number;
    roas_range_high: number;
    confidence_level: ConfidenceLevel;
    explanation: string;
  };
  confidence_levels: {
    revenue: ConfidenceLevel;
    roas: ConfidenceLevel;
    spend: ConfidenceLevel;
    conversions: ConfidenceLevel;
  };
  trend: Array<{
    date: string;
    revenue: number;
    spend: number;
    roas: number;
    roas_range_low: number;
    roas_range_high: number;
    revenue_low: number;
    revenue_high: number;
  }>;
}

export type ChannelDetailScenario =
  | "steady"
  | "loading"
  | "error"
  | "not_found"
  | "updating";
