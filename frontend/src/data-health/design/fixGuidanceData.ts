import type {
  FixGuidanceCardProps,
  FixGuidanceImpact,
  FixGuidanceIssue,
  FixGuidanceSeverity,
  SecondaryActionType,
} from "./fixGuidanceTypes";

/** Serializable seed rows — wire to API later (Constitution §8.3). */
export interface FixGuidanceSeedRow {
  id: string;
  severity: FixGuidanceSeverity;
  platformKey?: string;
  issue: FixGuidanceIssue;
  impact: FixGuidanceImpact;
  primaryLabel: string;
  primaryEstimatedTime?: string;
  secondaryLabel: string;
  secondaryType: SecondaryActionType;
  correlationId?: string;
  isDismissible: boolean;
  /** ISO time when issue was detected (or omit for “now” in demo). */
  timestamp?: string;
}

export const FIX_GUIDANCE_SEED: FixGuidanceSeedRow[] = [
  {
    id: "meta-fix",
    severity: "caution",
    platformKey: "meta",
    issue: {
      category: "sync_stale",
      title: "Meta Ads sync is stale",
      description: "(last sync: 2 hours ago)",
    },
    impact: {
      description:
        "This may affect attribution accuracy for Facebook and Instagram campaigns.",
      affectedChannels: ["Facebook", "Instagram"],
      monetaryRisk: "Attribution uncertainty: ±$12K",
    },
    primaryLabel: "Reconnect Meta Ads",
    primaryEstimatedTime: "Takes ~30 seconds",
    secondaryLabel: "View Sync Logs",
    secondaryType: "investigate",
    correlationId: "corr_dh_meta_8f2a9c1e",
    isDismissible: true,
    timestamp: "2026-03-22T11:40:00.000Z",
  },
  {
    id: "tiktok-fix",
    severity: "critical",
    platformKey: "tiktok",
    issue: {
      category: "authentication_expired",
      title: "TikTok authentication expired",
      description: "(OAuth token invalid — error 401)",
    },
    impact: {
      description:
        "New data cannot be fetched. Attribution will use cached data from Mar 20 until re-authenticated.",
      monetaryRisk: "Campaign attribution unavailable for TikTok spend",
    },
    primaryLabel: "Re-authenticate TikTok",
    primaryEstimatedTime: "~5 min to resolve",
    secondaryLabel: "Check permissions",
    secondaryType: "investigate",
    correlationId: "corr_dh_tt_441b0a2d",
    isDismissible: true,
    timestamp: "2026-03-22T12:55:00.000Z",
  },
  {
    id: "google-rate",
    severity: "caution",
    platformKey: "google_ads",
    issue: {
      category: "rate_limited",
      title: "Google Ads rate limit approaching",
      description: "(85% of daily quota used)",
    },
    impact: {
      description: "Sync delays may occur within 4 hours. Historical data is safe.",
    },
    primaryLabel: "Request quota increase",
    secondaryLabel: "Dismiss for 24h",
    secondaryType: "defer",
    correlationId: "corr_dh_ga_90ee3310",
    isDismissible: true,
    timestamp: "2026-03-22T12:40:00.000Z",
  },
];

export function seedRowsToProps(
  rows: FixGuidanceSeedRow[],
  handlers: {
    onNavigate: () => void;
    onDismiss: (id: string) => void;
  },
): FixGuidanceCardProps[] {
  return rows.map((row) => ({
    id: row.id,
    severity: row.severity,
    platformKey: row.platformKey,
    issue: row.issue,
    impact: row.impact,
    correlationId: row.correlationId,
    timestamp: row.timestamp ?? new Date().toISOString(),
    isDismissible: row.isDismissible,
    onDismiss: row.isDismissible ? () => handlers.onDismiss(row.id) : undefined,
    remediation: {
      primary: {
        label: row.primaryLabel,
        estimatedTime: row.primaryEstimatedTime,
        action: handlers.onNavigate,
      },
      secondary: {
        label: row.secondaryLabel,
        type: row.secondaryType,
        action:
          row.secondaryType === "dismiss"
            ? () => handlers.onDismiss(row.id)
            : handlers.onNavigate,
      },
    },
  }));
}
