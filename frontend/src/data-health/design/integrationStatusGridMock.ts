/**
 * Seed data for Per-Integration Status Grid — mock/API-shaped; scores are illustrative only.
 */

import type { IntegrationStatusCard } from "./integrationStatusGridTypes";

export function buildIntegrationStatusSeed(handlers: {
  onNavigate: () => void;
  onSyncNow?: (integrationId: string) => void;
}): IntegrationStatusCard[] {
  const { onNavigate, onSyncNow } = handlers;

  const cards: IntegrationStatusCard[] = [
    {
      id: "int_stripe",
      platform: "stripe",
      platformIconKey: "stripe",
      displayName: "Stripe",
      status: {
        state: "healthy",
        score: 94,
        thresholdText: "Score ≥ 70",
      },
      sync: {
        lastSyncAt: new Date(Date.now() - 2 * 60 * 1000).toISOString(),
        relativeTime: "2m ago",
        staleness: "fresh",
      },
      revenueMatch: { percentage: 100, status: "verified" },
      actions: {
        primary: { label: "Sync Now", action: () => onSyncNow?.("int_stripe") ?? onNavigate() },
        secondary: { label: "View Logs", action: onNavigate },
      },
    },
    {
      id: "int_google_ads",
      platform: "google_ads",
      platformIconKey: "google_ads",
      displayName: "Google Ads",
      status: {
        state: "healthy",
        score: 87,
        thresholdText: "Score ≥ 70",
      },
      sync: {
        lastSyncAt: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
        relativeTime: "5m ago",
        staleness: "fresh",
      },
      revenueMatch: { percentage: 98, status: "verified" },
      actions: {
        secondary: { label: "View Logs", action: onNavigate },
      },
    },
    {
      id: "int_meta",
      platform: "meta",
      platformIconKey: "meta",
      displayName: "Meta Ads",
      status: {
        state: "needs_review",
        score: 58,
        thresholdText: "Amber if sync > 2hrs",
      },
      sync: {
        lastSyncAt: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
        relativeTime: "2h ago",
        staleness: "stale",
      },
      revenueMatch: { percentage: 72, status: "partial" },
      fixGuidanceActive: true,
      actions: {
        primary: { label: "Reconnect", action: onNavigate },
        secondary: { label: "View Logs", action: onNavigate },
      },
    },
    {
      id: "int_tiktok",
      platform: "tiktok",
      platformIconKey: "tiktok",
      displayName: "TikTok",
      status: {
        state: "critical",
        score: 23,
        thresholdText: "Critical if score < 50",
      },
      sync: {
        lastSyncAt: new Date(Date.now() - 26 * 60 * 60 * 1000).toISOString(),
        relativeTime: "1d ago",
        staleness: "stale",
      },
      revenueMatch: { percentage: 0, status: "unverified" },
      fixGuidanceActive: true,
      actions: {
        primary: { label: "Re-auth", action: onNavigate, destructive: true },
        secondary: { label: "View Logs", action: onNavigate },
      },
    },
    {
      id: "int_klaviyo",
      platform: "klaviyo",
      platformIconKey: "klaviyo",
      displayName: "Klaviyo",
      status: {
        state: "needs_review",
        score: 62,
        thresholdText: "No webhook configured",
      },
      sync: {
        lastSyncAt: "",
        relativeTime: "—",
        staleness: "stale",
      },
      revenueMatch: { percentage: 0, status: "unverified" },
      actions: {
        primary: { label: "Setup", action: onNavigate },
        secondary: { label: "View Logs", action: onNavigate },
      },
    },
  ];

  return cards;
}
