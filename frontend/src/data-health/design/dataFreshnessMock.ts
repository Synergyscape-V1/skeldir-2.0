import { createElement } from "react";
import { PlatformIcon } from "./PlatformIcon";
import type { FreshnessIntegration, FreshnessHistoryPoint, HistorySyncStatus } from "./dataFreshnessTypes";

function isoHour(base: Date, hoursAgo: number): string {
  const d = new Date(base.getTime() - hoursAgo * 60 * 60 * 1000);
  d.setUTCMinutes(0, 0, 0);
  return d.toISOString();
}

/** Deterministic “random” 0..1 from string + index. */
function hash01(seed: string, i: number): number {
  let h = 0;
  const s = `${seed}:${i}`;
  for (let k = 0; k < s.length; k++) h = Math.imul(31, h) + s.charCodeAt(k) | 0;
  return ((h >>> 0) % 10000) / 10000;
}

function buildHistory168(seed: string, now: Date): FreshnessHistoryPoint[] {
  const out: FreshnessHistoryPoint[] = [];
  for (let h = 167; h >= 0; h--) {
    const r = hash01(seed, h);
    let status: HistorySyncStatus = "success";
    let duration: number | undefined = 1 + Math.round(r * 40) / 10;
    let delayMinutes: number | undefined;

    // Stripe: mostly green
    if (seed === "stripe") {
      if (r < 0.03) status = "no_data";
      else if (r < 0.06) {
        status = "stale";
        delayMinutes = 8 + Math.round(r * 15);
      }
    }
    // Google: mid-run gray gap windows
    if (seed === "google") {
      if (r < 0.08) status = "no_data";
      else if (r < 0.11) {
        status = "stale";
        delayMinutes = 10 + Math.round(r * 12);
      }
    }
    // Meta: streak of amber + errors toward “now”
    if (seed === "meta") {
      if (h < 18 && h > 12) {
        status = "stale";
        delayMinutes = 12 + Math.round(r * 10);
      } else if (h <= 12 && h > 8) {
        status = "error";
        duration = undefined;
      } else if (r < 0.05) {
        status = "stale";
        delayMinutes = 20 + Math.round(r * 20);
      }
    }
    // TikTok: errors
    if (seed === "tiktok") {
      if (h < 30 && h > 20) {
        status = r < 0.35 ? "error" : "stale";
        if (status === "stale") delayMinutes = 40 + Math.round(r * 30);
      } else if (r < 0.12) status = "no_data";
    }

    out.push({
      timestamp: isoHour(now, h),
      status,
      duration: status === "error" || status === "no_data" ? undefined : duration,
      delayMinutes,
    });
  }
  return out;
}

function worstStreakStaleOrError(history: FreshnessHistoryPoint[]): number {
  let cur = 0;
  let max = 0;
  for (const pt of history) {
    if (pt.status === "stale" || pt.status === "error") {
      cur += 1;
      max = Math.max(max, cur);
    } else {
      cur = 0;
    }
  }
  return max;
}

/** Ensures at least one row qualifies for Fix Guidance (≥3 consecutive stale/error). */
function ensureFixStreak(seed: string, history: FreshnessHistoryPoint[]): FreshnessHistoryPoint[] {
  if (seed !== "meta" || worstStreakStaleOrError(history) >= 3) return history;
  const copy = history.slice();
  for (let i = copy.length - 3; i < copy.length; i++) {
    copy[i] = {
      ...copy[i],
      status: "stale",
      delayMinutes: 45,
      duration: undefined,
    };
  }
  return copy;
}

export function buildMockIntegrations(now = new Date()): FreshnessIntegration[] {
  const stripeH = ensureFixStreak("stripe", buildHistory168("stripe", now));
  const googleH = ensureFixStreak("google", buildHistory168("google", now));
  const metaH = ensureFixStreak("meta", buildHistory168("meta", now));
  const tiktokH = ensureFixStreak("tiktok", buildHistory168("tiktok", now));

  const integrations: FreshnessIntegration[] = [
    {
      id: "stripe_001",
      platform: "stripe",
      displayName: "Stripe",
      icon: createElement(PlatformIcon, { platform: "stripe", size: 20 }),
      currentStatus: {
        state: "fresh",
        lastSyncAt: new Date(now.getTime() - 2 * 60 * 1000).toISOString(),
        nextScheduledSync: new Date(now.getTime() + 28 * 60 * 1000).toISOString(),
      },
      history: stripeH,
      healthScore: 98,
    },
    {
      id: "google_ads_001",
      platform: "google_ads",
      displayName: "Google Ads",
      icon: createElement(PlatformIcon, { platform: "google_ads", size: 20 }),
      currentStatus: {
        state: "fresh",
        lastSyncAt: new Date(now.getTime() - 5 * 60 * 1000).toISOString(),
      },
      history: googleH,
      healthScore: 94,
    },
    {
      id: "meta_ads_001",
      platform: "meta",
      displayName: "Meta Ads",
      icon: createElement(PlatformIcon, { platform: "meta", size: 20 }),
      currentStatus: {
        state: "aging",
        lastSyncAt: new Date(now.getTime() - 2 * 60 * 60 * 1000).toISOString(),
      },
      history: metaH,
      healthScore: 72,
    },
    {
      id: "tiktok_001",
      platform: "tiktok",
      displayName: "TikTok",
      icon: createElement(PlatformIcon, { platform: "tiktok", size: 20 }),
      currentStatus: {
        state: "error",
        lastSyncAt: new Date(now.getTime() - 26 * 60 * 60 * 1000).toISOString(),
      },
      history: tiktokH,
      healthScore: 38,
    },
  ];

  return integrations;
}
