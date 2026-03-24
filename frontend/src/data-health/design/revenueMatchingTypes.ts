import type { ReactNode } from "react";

export type RevenuePlatformKey =
  | "facebook"
  | "google_ads"
  | "tiktok"
  | "snapchat"
  | "klaviyo";

export type MatchCategory = "matched" | "flagged" | "severe" | "unmatched";

export type DiscrepancyDirection = "over" | "under" | "matched";

export type VerificationConfidence = "high" | "medium" | "low";

export type AttributionMethod = "webhook" | "api_poll" | "manual_import";

export interface RevenueBreakdownRow {
  id: string;
  platform: RevenuePlatformKey;
  displayName: string;
  platformIcon: ReactNode;
  claimed: string;
  verified: string;
  discrepancy: {
    amount: string;
    percentage: string;
    direction: DiscrepancyDirection;
  };
  category: MatchCategory;
  confidence: VerificationConfidence;
  lastVerifiedAt: string;
  attributionMethod: AttributionMethod;
}

export interface RevenueMatchingBreakdownProps {
  period: {
    start: string;
    end: string;
    label: string;
  };
  summary: {
    totalClaimed: string;
    totalVerified: string;
    totalDiscrepancy: string;
    matchRate: string;
  };
  breakdown: RevenueBreakdownRow[];
  filters?: {
    category?: "all" | MatchCategory;
    minDiscrepancy?: string;
  };
  onRowClick: (platformId: string) => void;
  onExport: () => void;
  onRefresh?: () => void;
}
