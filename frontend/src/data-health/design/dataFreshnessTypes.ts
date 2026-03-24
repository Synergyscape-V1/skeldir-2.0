import type { ReactNode } from "react";

export type DataFreshnessPlatform =
  | "stripe"
  | "paypal"
  | "google_ads"
  | "meta"
  | "tiktok"
  | "linkedin";

export type CurrentFreshnessState = "fresh" | "aging" | "stale" | "error";

export type HistorySyncStatus = "success" | "stale" | "error" | "no_data";

export interface FreshnessHistoryPoint {
  timestamp: string;
  status: HistorySyncStatus;
  /** Sync duration in seconds (tooltip). */
  duration?: number;
  /** When status is stale, delay in minutes (drives aging vs stale bucket). */
  delayMinutes?: number;
}

export interface FreshnessIntegration {
  id: string;
  platform: DataFreshnessPlatform;
  displayName: string;
  icon: ReactNode;
  currentStatus: {
    state: CurrentFreshnessState;
    lastSyncAt: string;
    nextScheduledSync?: string;
  };
  history: FreshnessHistoryPoint[];
  /** 0–100; tints row background subtly when low. */
  healthScore: number;
}

export type FreshnessTimeWindow = "24h" | "7d";

export interface DataFreshnessTimelineProps {
  integrations: FreshnessIntegration[];
  timeWindow?: FreshnessTimeWindow;
  onIntegrationClick: (id: string) => void;
  onSyncNow?: (id: string) => void;
  maxHeight?: number;
  /** Opens help / constitution copy (optional). */
  onHelpClick?: () => void;
  /** Opens aggregated sync logs (optional). */
  onLogsClick?: () => void;
}
