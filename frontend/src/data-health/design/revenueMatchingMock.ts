import { createElement } from "react";
import { PlatformIcon } from "./PlatformIcon";
import type { RevenueBreakdownRow, RevenueMatchingBreakdownProps } from "./revenueMatchingTypes";

function icon(platform: string) {
  const size = 24;
  return createElement(PlatformIcon, { platform, size });
}

export const DEFAULT_REVENUE_PERIOD: RevenueMatchingBreakdownProps["period"] = {
  start: "2026-02-20T00:00:00.000Z",
  end: "2026-03-22T23:59:59.999Z",
  label: "Last 30 days",
};

export const DEFAULT_REVENUE_SUMMARY: RevenueMatchingBreakdownProps["summary"] = {
  totalClaimed: "$523,400",
  totalVerified: "$438,200",
  totalDiscrepancy: "-$85,200",
  matchRate: "83.7%",
};

export const DEFAULT_REVENUE_BREAKDOWN: RevenueBreakdownRow[] = [
  {
    id: "fb_ads",
    platform: "facebook",
    displayName: "Facebook Ads",
    platformIcon: icon("facebook"),
    claimed: "$52,300",
    verified: "$43,800",
    discrepancy: {
      amount: "-$8,500",
      percentage: "-16.3%",
      direction: "over",
    },
    category: "severe",
    confidence: "high",
    lastVerifiedAt: "2026-03-22T12:58:00.000Z",
    attributionMethod: "webhook",
  },
  {
    id: "google_search",
    platform: "google_ads",
    displayName: "Google Search",
    platformIcon: icon("google_ads"),
    claimed: "$89,400",
    verified: "$87,200",
    discrepancy: {
      amount: "-$2,200",
      percentage: "-2.5%",
      direction: "over",
    },
    category: "flagged",
    confidence: "high",
    lastVerifiedAt: "2026-03-22T12:55:00.000Z",
    attributionMethod: "webhook",
  },
  {
    id: "tiktok",
    platform: "tiktok",
    displayName: "TikTok",
    platformIcon: icon("tiktok"),
    claimed: "$12,000",
    verified: "$11,940",
    discrepancy: {
      amount: "-$60",
      percentage: "-0.5%",
      direction: "over",
    },
    category: "matched",
    confidence: "high",
    lastVerifiedAt: "2026-03-22T12:59:00.000Z",
    attributionMethod: "webhook",
  },
  {
    id: "klaviyo",
    platform: "klaviyo",
    displayName: "Klaviyo",
    platformIcon: icon("klaviyo"),
    claimed: "$8,500",
    verified: "—",
    discrepancy: {
      amount: "—",
      percentage: "—",
      direction: "matched",
    },
    category: "unmatched",
    confidence: "low",
    lastVerifiedAt: "2026-03-15T10:00:00.000Z",
    attributionMethod: "manual_import",
  },
];

/** Optional copy for expanded waterfall — from API in production */
export const WATERFALL_COPY: Record<
  string,
  {
    platformClaimed: string;
    platformAdjusted: string;
    adjustedNote: string;
    verified: string;
    gap: string;
    overlap: string;
    overlapNote: string;
    skeldirAttributed: string;
    bullets: string[];
  }
> = {
  fb_ads: {
    platformClaimed: "$52,300",
    platformAdjusted: "$51,100",
    adjustedNote: "Refunds: -$800, Fees: -$400",
    verified: "$43,800",
    gap: "-$7,300",
    overlap: "-$1,200",
    overlapNote: "Double-click attribution",
    skeldirAttributed: "$43,800",
    bullets: [
      "Duplicate pixel firing on checkout page",
      "Refunds not reflected in platform API",
      "Cross-device attribution gaps",
    ],
  },
  google_search: {
    platformClaimed: "$89,400",
    platformAdjusted: "$88,900",
    adjustedNote: "Fees: -$500",
    verified: "$87,200",
    gap: "-$1,700",
    overlap: "-$500",
    overlapNote: "Attribution window overlap",
    skeldirAttributed: "$87,200",
    bullets: ["Minor timing lag vs Stripe settlement", "Review campaign tagging"],
  },
  tiktok: {
    platformClaimed: "$12,000",
    platformAdjusted: "$11,980",
    adjustedNote: "Fees: -$20",
    verified: "$11,940",
    gap: "-$40",
    overlap: "-$20",
    overlapNote: "Rounding",
    skeldirAttributed: "$11,940",
    bullets: ["Within acceptable variance"],
  },
};
