/**
 * Per-Integration Status Grid — Interface 8 / Constitution §7.1
 * Scores and integrity state are API-sourced; UI does not compute scores.
 */

import type { ReactNode } from "react";

export type IntegrationPlatformKey =
  | "stripe"
  | "paypal"
  | "google_ads"
  | "meta"
  | "tiktok"
  | "linkedin"
  | "klaviyo";

export type IntegrityState = "healthy" | "needs_review" | "critical";

export type Staleness = "fresh" | "aging" | "stale";

export type RevenueVerificationStatus = "verified" | "partial" | "unverified";

export interface IntegrationStatusCard {
  id: string;
  platform: IntegrationPlatformKey;
  /** PlatformIcon key — may alias e.g. googleads → google_ads */
  platformIconKey: string;
  displayName: string;
  /** Optional: override default icon; otherwise PlatformIcon(platformIconKey) */
  icon?: ReactNode;

  status: {
    state: IntegrityState;
    /** 0–100 composite integrity score (backend) */
    score: number;
    /** Embedded threshold copy — Constitution §7.1 */
    thresholdText: string;
  };

  sync: {
    lastSyncAt: string;
    relativeTime: string;
    staleness: Staleness;
    nextScheduledSync?: string;
  };

  revenueMatch?: {
    percentage: number;
    status: RevenueVerificationStatus;
  };

  actions: {
    primary?: {
      label: string;
      action: () => void;
      destructive?: boolean;
    };
    secondary?: {
      label: string;
      action: () => void;
    };
  };

  /** When true, dashed ring indicates linked Fix Guidance (§7.2) */
  fixGuidanceActive?: boolean;
  correlationId?: string;
}

export type PerIntegrationSortBy = "severity" | "name" | "recent";

export interface PerIntegrationStatusGridProps {
  integrations: IntegrationStatusCard[];
  /** Default: severity (critical first) */
  sortBy?: PerIntegrationSortBy;
  onCardClick: (integrationId: string) => void;
  onRefreshAll?: () => void;
}
