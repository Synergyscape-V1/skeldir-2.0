export interface ChannelROAS {
  estimate: number;
  lower: number;
  upper: number;
  bucket: "narrow" | "medium" | "wide";
  formattedEstimate: string;
  formattedLower: string;
  formattedUpper: string;
  rangeLabel: string;
}

export type TrendDirection = "up" | "down" | "neutral";

/** API-shaped trend copy; display + light sorting only (no recomputation of metrics). */
export interface ChannelTrend {
  direction: TrendDirection;
  /** e.g. "↑ 7%" — from attribution API */
  value: string;
  period?: string;
}

export interface ChannelData {
  channelId: string;
  channelName: string;
  platform: string;
  colorIndex: number;
  spend: number;
  spendFormatted: string;
  verifiedRevenue: number;
  verifiedRevenueFormatted: string;
  discrepancyPct: number;
  verificationStatus: "verified" | "partial" | "unverified";
  /** Revenue ground-truth source label (e.g. webhook provider). */
  revenueSource?: string;
  lastSyncLabel?: string;
  /** When partial, optional match % for disclosure line. */
  verificationPartialPct?: number;
  attributionWeight: number;
  attributionMethod: string;
  roas: ChannelROAS;
  agreementScore: number;
  divergenceFlag: boolean;
  /** Cost per lead — numeric for ordering; display uses `cplFormatted`. */
  cpl: number;
  cplFormatted: string;
  conversions: number;
  trend: ChannelTrend;
}

export interface AvailableChannel {
  channelId: string;
  channelName: string;
  platform: string;
  hasData: boolean;
}

export const DATA_COLORS: Record<number, string> = {
  1: "#3B82F6",  // Google Ads — vivid blue (blue-500)
  2: "#8B5CF6",  // Meta — vivid purple (violet-500)
  3: "#EC4899",  // TikTok — vivid pink (pink-500)
  4: "#10B981",  // LinkedIn — vivid teal (emerald-500)
  5: "#E60023",
  6: "#00C2FF",
};

export const BUCKET_CONFIG: Record<string, { color: string; label: string }> = {
  narrow: { color: "#10B981", label: "Narrow" },
  medium: { color: "#F59E0B", label: "Medium" },
  wide: { color: "#EF4444", label: "Wide" },
};

/** Dark/light pair per channel identity color for two-tone HDI bar encoding.
 *  Dark = 500-weight (high-density left segment), Light = 400-weight (upper taper right segment). */
export const CHANNEL_BAR_COLORS: Record<number, { dark: string; light: string }> = {
  1: { dark: "#3B82F6", light: "#60A5FA" },  // Google Ads — blue-500 / blue-400
  2: { dark: "#8B5CF6", light: "#A78BFA" },  // Meta — violet-500 / violet-400
  3: { dark: "#EC4899", light: "#F472B6" },  // TikTok — pink-500 / pink-400
  4: { dark: "#10B981", light: "#34D399" },  // LinkedIn — emerald-500 / emerald-400
  5: { dark: "#E60023", light: "#FF4D6A" },  // (reserve)
  6: { dark: "#00A3CC", light: "#00C2FF" },  // (reserve)
};
