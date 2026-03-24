import type { ReactNode } from "react";
import type { ChannelData } from "./types";

/** Locked horizontal domain — keep in sync with `ComparisonTable` ROAS mini-bars (DOMAIN_MIN / DOMAIN_MAX). */
export const CC_ROAS_SCALE = { min: 0, max: 6 } as const;

export type ROASBucket = "narrow" | "medium" | "wide";

export type SampleSizeIndicator = "robust" | "limited" | "insufficient";

export type AttributionModel = "bayesian" | "linear" | "time_decay";

export type ROASViewMode = "aligned" | "overlay";

export type ROASSortMode = "point_estimate" | "lower_bound" | "confidence_width" | "priority";

export interface ROASChannelRow {
  channelId: string;
  channelName: string;
  channelIcon: ReactNode;
  platform: string;
  roas: {
    pointEstimate: number;
    lower: number;
    upper: number;
    formattedPoint: string;
    formattedLower: string;
    formattedUpper: string;
  };
  bucket: ROASBucket;
  /** Posterior relative width \((upper-lower) / pointEstimate\) — drives bucket when recomputed. */
  relativeWidth: number;
  sampleSizeIndicator?: SampleSizeIndicator;
  attributionModel: AttributionModel;
  /** Original channel color index for overlay stroke accents */
  colorIndex: number;
}

export interface ComparisonScale {
  min: number;
  max: number;
  ticks: number[];
}

export interface ROASCredibleIntervalComparisonProps {
  channels: ROASChannelRow[];
  comparisonScale: ComparisonScale;
  confidenceLevel: number;
  viewMode: ROASViewMode;
  onChannelSelect?: (id: string) => void;
  sortBy?: ROASSortMode;
  /** e.g. "Last 30 days" */
  periodLabel?: string;
  onExport?: () => void;
}

export interface CredibleIntervalBarProps {
  pointEstimate: number;
  lower: number;
  upper: number;
  scaleMin: number;
  scaleMax: number;
  /** Channel identity index — drives two-tone bar colors (see `CHANNEL_BAR_COLORS`). */
  colorIndex: number;
  showPointEstimate: boolean;
  isOverlayMode?: boolean;
  plotWidth: number;
  barHeight: number;
  yOffset: number;
}

/** Spec §5.2 — relative precision vs median. */
export function bucketFromRelativeWidth(relativeWidth: number): ROASBucket {
  if (relativeWidth < 0.25) return "narrow";
  if (relativeWidth < 0.5) return "medium";
  return "wide";
}

export function relativeWidthFromRoas(lower: number, upper: number, pointEstimate: number): number {
  const pe = Math.max(pointEstimate, 1e-6);
  return (upper - lower) / pe;
}

function mapAttribution(m: string): AttributionModel {
  if (m === "linear" || m === "time_decay") return m;
  return "bayesian";
}

function sampleIndicatorFromAgreement(score: number): SampleSizeIndicator | undefined {
  if (score >= 0.75) return "robust";
  if (score >= 0.55) return "limited";
  return "insufficient";
}

/** Map redesign `ChannelData` into spec row model (icons supplied by caller). */
export function channelDataToRows(
  channels: ChannelData[],
  iconFor: (platform: string) => ReactNode
): ROASChannelRow[] {
  return channels.map((c) => {
    const { lower, upper, estimate: pointEstimate } = c.roas;
    const rw = relativeWidthFromRoas(lower, upper, pointEstimate);
    const computed = bucketFromRelativeWidth(rw);
    return {
      channelId: c.channelId,
      channelName: c.channelName,
      channelIcon: iconFor(c.platform),
      platform: c.platform,
      roas: {
        pointEstimate,
        lower,
        upper,
        formattedPoint: c.roas.formattedEstimate,
        formattedLower: c.roas.formattedLower,
        formattedUpper: c.roas.formattedUpper,
      },
      bucket: c.roas.bucket ?? computed,
      relativeWidth: rw,
      sampleSizeIndicator: sampleIndicatorFromAgreement(c.agreementScore),
      attributionModel: mapAttribution(c.attributionMethod),
      colorIndex: c.colorIndex,
    };
  });
}

export function buildComparisonTicks(min: number, max: number, step = 0.5): number[] {
  const n = Math.max(0, Math.round((max - min) / step));
  return Array.from({ length: n + 1 }, (_, i) => Number((min + i * step).toFixed(4)));
}

export function sortRows(rows: ROASChannelRow[], sortBy: ROASSortMode): ROASChannelRow[] {
  const next = [...rows];
  const pri = (b: ROASBucket) => (b === "narrow" ? 0 : b === "medium" ? 1 : 2);
  switch (sortBy) {
    case "point_estimate":
      return next.sort((a, b) => b.roas.pointEstimate - a.roas.pointEstimate);
    case "lower_bound":
      return next.sort((a, b) => b.roas.lower - a.roas.lower);
    case "confidence_width":
      return next.sort(
        (a, b) => a.roas.upper - a.roas.lower - (b.roas.upper - b.roas.lower)
      );
    case "priority":
    default:
      return next.sort((a, b) => {
        const dp = pri(a.bucket) - pri(b.bucket);
        if (dp !== 0) return dp;
        return b.roas.pointEstimate - a.roas.pointEstimate;
      });
  }
}

/** Pairwise interval overlap as % of the narrower interval length (0–100). */
export function pairwiseOverlapPct(
  a: { lower: number; upper: number },
  b: { lower: number; upper: number }
): number {
  const lo = Math.max(a.lower, b.lower);
  const hi = Math.min(a.upper, b.upper);
  const inter = Math.max(0, hi - lo);
  const wA = Math.max(1e-9, a.upper - a.lower);
  const wB = Math.max(1e-9, b.upper - b.lower);
  const narrower = Math.min(wA, wB);
  return Math.min(100, (inter / narrower) * 100);
}

export function findMaxOverlapPair(rows: ROASChannelRow[]): {
  a: ROASChannelRow;
  b: ROASChannelRow;
  pct: number;
} | null {
  if (rows.length < 2) return null;
  let best: { a: ROASChannelRow; b: ROASChannelRow; pct: number } | null = null;
  for (let i = 0; i < rows.length; i++) {
    for (let j = i + 1; j < rows.length; j++) {
      const pct = pairwiseOverlapPct(rows[i].roas, rows[j].roas);
      if (!best || pct > best.pct) best = { a: rows[i], b: rows[j], pct };
    }
  }
  return best;
}
