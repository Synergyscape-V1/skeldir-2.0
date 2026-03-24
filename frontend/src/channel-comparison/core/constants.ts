import type { DateRangeValue, PlatformType } from "../../types/channel";

export const CHANNEL_COLORS = ["var(--data-1)", "var(--data-2)", "var(--data-3)", "var(--data-4)"] as const;

export const DEFAULT_CHANNEL_IDS = ["ch_google_ads", "ch_facebook_ads", "ch_pinterest_ads"] as const;

export const VALID_DATE_RANGES: DateRangeValue[] = [
  "last_7_days",
  "last_30_days",
  "last_60_days",
  "last_90_days",
];

export const DATE_RANGE_LABELS: Record<DateRangeValue, string> = {
  last_7_days: "Last 7 Days",
  last_30_days: "Last 30 Days",
  last_60_days: "Last 60 Days",
  last_90_days: "Last 90 Days",
  custom: "Custom",
};

export function platformMeta(platformType: PlatformType): { iconSrc: string; label: string } {
  if (platformType === "google_ads") return { iconSrc: "/assets/platform-icons/google-ads.svg", label: "Google Ads" };
  if (platformType === "facebook_ads") return { iconSrc: "/assets/platform-icons/meta-ads.svg", label: "Meta Ads" };
  if (platformType === "tiktok_ads") return { iconSrc: "/assets/platform-icons/tiktok-ads.svg", label: "TikTok Ads" };
  return { iconSrc: "/assets/platform-icons/pinterest-ads.svg", label: "Pinterest Ads" };
}

export function displayChannelName(name: string, platformType: PlatformType): string {
  if (platformType === "facebook_ads") return "Meta Ads";
  return name;
}
