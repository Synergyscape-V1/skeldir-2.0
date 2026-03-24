import type { DataIssue } from "./types";
import type { MetricStatus } from "./types";

export const METRICS = [
  {
    key: "trackingCoverage" as const,
    title: "Tracking Coverage",
    target: 95,
    description: "Percentage of pages with Skeldir tag installed.",
  },
  {
    key: "utmConsistency" as const,
    title: "UTM Consistency Score",
    target: 90,
    description: "Taxonomy health rating.",
  },
  {
    key: "revenueMatchRate" as const,
    title: "Revenue Match Rate",
    target: 95,
    description: "Webhook vs. tracking event alignment.",
  },
];

export const INTEGRATIONS = [
  {
    id: "meta",
    name: "Meta Ads",
    icon: "/assets/platform-icons/meta-ads.svg",
    status: "Connected",
    level: "connected" as const,
    detail: "Synced 2 minutes ago",
    primaryAction: "Test Connection",
    secondaryAction: "Disconnect",
  },
  {
    id: "google",
    name: "Google Ads",
    icon: "/assets/platform-icons/google-ads.svg",
    status: "Connected",
    level: "connected" as const,
    detail: "Synced 5 minutes ago",
    primaryAction: "Test Connection",
    secondaryAction: "Disconnect",
  },
  {
    id: "stripe",
    name: "Stripe",
    icon: "/assets/platform-icons/stripe.svg",
    status: "Connected",
    level: "connected" as const,
    detail: "Synced 10 minutes ago",
    primaryAction: "Test Connection",
    secondaryAction: "Disconnect",
  },
  {
    id: "tiktok",
    name: "TikTok Ads",
    icon: "/assets/platform-icons/tiktok-ads.svg",
    status: "Disconnected",
    level: "critical" as const,
    detail: "Connection Lost",
    primaryAction: "Reconnect",
  },
  {
    id: "shopify",
    name: "Shopify",
    icon: "/assets/platform-icons/shopify-icon.svg",
    status: "Expiring Soon",
    level: "warning" as const,
    detail: "Expires in 3 days",
    primaryAction: "Refresh Token",
  },
];

export const SEVERITY_ORDER: Array<DataIssue["severity"]> = ["critical", "warning", "info"];

export const SEVERITY_TITLE: Record<DataIssue["severity"], string> = {
  critical: "Critical",
  warning: "Warning",
  info: "Info",
};

export const SEVERITY_IMPACT: Record<DataIssue["severity"], string> = {
  critical: "Impact: 40% of conversions untracked",
  warning: "Impact: Medium confidence impact",
  info: "Impact: Preventive",
};

export const SEVERITY_STATUS: Record<DataIssue["severity"], string> = {
  critical: "Status: Active",
  warning: "Status: Active",
  info: "Status: Scheduled",
};

export const SEVERITY_ACTION: Record<DataIssue["severity"], string> = {
  critical: "Fix Now",
  warning: "Review Tags",
  info: "Refresh Token",
};

export function metricConfidence(status: MetricStatus): string {
  if (status === "good") return "High Confidence";
  if (status === "warning") return "Medium Confidence";
  return "Low Confidence";
}

export function grouped(issues: DataIssue[]) {
  return {
    critical: issues.filter((item) => item.severity === "critical"),
    warning: issues.filter((item) => item.severity === "warning"),
    info: issues.filter((item) => item.severity === "info"),
  };
}
