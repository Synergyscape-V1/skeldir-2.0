/**
 * MetricMatrix — Dense Small-Multiples Grid
 *
 * The centerpiece of A4-ATLAS. A heatmap-colored matrix where:
 * - Rows = channels
 * - Columns = metrics (Revenue, ROAS, Ad Spend, CPA, Conversions)
 *
 * Each cell contains:
 * - Formatted value (monospace)
 * - Delta vs average indicator
 * - Heatmap background tint (best=emerald, worst=red, middle=neutral)
 * - Mini trend sparkline
 *
 * All values are pre-formatted (Zero Mental Math).
 * Heatmap ranking is DISPLAY logic only — just "is this the max/min in the group."
 */

import React, { useMemo } from 'react';
import { cn } from '@/lib/utils';
import { getPlatformLogo } from '@/pages/channel-comparison/shared/platform-logos';
import type { ChannelComparisonEntry, ConfidenceTier } from '@/pages/channel-comparison/shared/types';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface MetricDef {
  key: string;
  label: string;
  getValue: (ch: ChannelComparisonEntry) => string;
  getDelta: (ch: ChannelComparisonEntry) => string | null;
  getDirection: (ch: ChannelComparisonEntry) => 'above' | 'below' | 'at' | null;
  /** Numeric extraction for heatmap ranking. Higher = better for most metrics. */
  getNumeric: (ch: ChannelComparisonEntry) => number;
  /** Whether higher is better (true) or lower is better (false, e.g. CPA) */
  higherIsBetter: boolean;
}

export interface MetricMatrixProps {
  channels: ChannelComparisonEntry[];
  className?: string;
}

// ---------------------------------------------------------------------------
// Metric Definitions
// ---------------------------------------------------------------------------

function parseUsd(s: string): number {
  return parseFloat(s.replace(/[$,]/g, '')) || 0;
}

const METRICS: MetricDef[] = [
  {
    key: 'revenue',
    label: 'Revenue',
    getValue: (ch) => ch.verifiedRevenue,
    getDelta: (ch) => ch.revenueVsAverage,
    getDirection: (ch) => ch.revenueDirection,
    getNumeric: (ch) => parseUsd(ch.verifiedRevenue),
    higherIsBetter: true,
  },
  {
    key: 'roas',
    label: 'ROAS',
    getValue: (ch) => ch.roas,
    getDelta: (ch) => ch.roasVsAverage,
    getDirection: (ch) => ch.roasDirection,
    getNumeric: (ch) => parseUsd(ch.roas),
    higherIsBetter: true,
  },
  {
    key: 'adSpend',
    label: 'Ad Spend',
    getValue: (ch) => ch.adSpend,
    getDelta: () => null,
    getDirection: () => null,
    getNumeric: (ch) => parseUsd(ch.adSpend),
    higherIsBetter: false, // lower spend, same output = better efficiency
  },
  {
    key: 'cpa',
    label: 'CPA',
    getValue: (ch) => ch.cpa,
    getDelta: () => null,
    getDirection: () => null,
    getNumeric: (ch) => parseUsd(ch.cpa),
    higherIsBetter: false, // lower CPA is better
  },
  {
    key: 'conversions',
    label: 'Conv.',
    getValue: (ch) => ch.conversions,
    getDelta: () => null,
    getDirection: () => null,
    getNumeric: (ch) => parseInt(ch.conversions.replace(/,/g, ''), 10) || 0,
    higherIsBetter: true,
  },
];

// ---------------------------------------------------------------------------
// Heatmap ranking
// ---------------------------------------------------------------------------

interface RankMap {
  /** 0 = best, channels.length - 1 = worst */
  [channelId: string]: number;
}

function buildRankMaps(
  channels: ChannelComparisonEntry[],
): Record<string, RankMap> {
  const maps: Record<string, RankMap> = {};

  for (const metric of METRICS) {
    const values = channels.map((ch) => ({
      id: ch.channelId,
      val: metric.getNumeric(ch),
    }));

    // Sort: best first
    const sorted = [...values].sort((a, b) =>
      metric.higherIsBetter ? b.val - a.val : a.val - b.val,
    );

    const rankMap: RankMap = {};
    sorted.forEach((item, i) => {
      rankMap[item.id] = i;
    });
    maps[metric.key] = rankMap;
  }

  return maps;
}

function heatmapClass(rank: number, total: number): string {
  if (total <= 1) return '';
  if (rank === 0) return 'bg-emerald-500/8';
  if (rank === total - 1) return 'bg-red-500/8';
  return '';
}

// ---------------------------------------------------------------------------
// Mini Trend Sparkline (inline SVG)
// ---------------------------------------------------------------------------

const TrendMini: React.FC<{ data: ChannelComparisonEntry['trendData']; color: string }> = ({
  data,
  color,
}) => {
  if (!data || data.length < 2) return null;

  const values = data.map((d) => d.roas);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  const w = 48;
  const h = 16;
  const pad = 2;

  const points = values
    .map((v, i) => {
      const x = pad + (i / (values.length - 1)) * (w - pad * 2);
      const y = h - pad - ((v - min) / range) * (h - pad * 2);
      return `${x},${y}`;
    })
    .join(' ');

  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} className="inline-block align-middle">
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0.7"
      />
    </svg>
  );
};

// ---------------------------------------------------------------------------
// Confidence Badge
// ---------------------------------------------------------------------------

const ConfidencePip: React.FC<{ tier: ConfidenceTier; margin: number }> = ({ tier, margin }) => {
  const styles: Record<ConfidenceTier, string> = {
    high: 'bg-emerald-500/15 text-emerald-400',
    medium: 'bg-amber-500/15 text-amber-400',
    low: 'bg-red-500/15 text-red-400',
  };
  return (
    <span
      className={cn(
        'inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-mono',
        styles[tier],
      )}
      title={`${tier} confidence, +/-${margin}% margin`}
    >
      {`\u00B1${margin}%`}
    </span>
  );
};

// ---------------------------------------------------------------------------
// Discrepancy Row
// ---------------------------------------------------------------------------

const DiscrepancyRow: React.FC<{ channels: ChannelComparisonEntry[] }> = ({ channels }) => (
  <div className="rounded-lg border border-border bg-card overflow-hidden">
    <div className="px-3 py-2 border-b border-border bg-muted/30">
      <h4 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
        Verification Discrepancy
      </h4>
    </div>
    <div className="grid gap-px bg-border" style={{ gridTemplateColumns: `repeat(${channels.length}, 1fr)` }}>
      {channels.map((ch) => {
        const severity =
          ch.discrepancyPercent > 20
            ? 'text-red-400'
            : ch.discrepancyPercent > 10
              ? 'text-amber-400'
              : 'text-emerald-400';
        return (
          <div key={ch.channelId} className="bg-card px-3 py-2 text-center">
            <div className="text-[10px] text-muted-foreground mb-0.5">{ch.channelName}</div>
            <div className={cn('text-xs font-mono font-semibold', severity)}>
              {ch.discrepancyPercent.toFixed(1)}%
            </div>
            <div className="text-[9px] text-muted-foreground/60 mt-0.5">
              {ch.platformClaimed} claimed / {ch.verified} verified
            </div>
          </div>
        );
      })}
    </div>
  </div>
);

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export const MetricMatrix: React.FC<MetricMatrixProps> = ({ channels, className }) => {
  const rankMaps = useMemo(() => buildRankMaps(channels), [channels]);

  return (
    <div className={cn('space-y-4', className)}>
      {/* Matrix Grid */}
      <div className="rounded-lg border border-border bg-card overflow-x-auto">
        <table className="w-full border-collapse text-xs">
          <thead>
            <tr className="border-b border-border bg-muted/30">
              {/* Channel column header */}
              <th className="text-left px-3 py-2 text-[10px] font-semibold text-muted-foreground uppercase tracking-wider sticky left-0 bg-muted/30 z-10 min-w-[140px]">
                Channel
              </th>
              {/* Metric column headers */}
              {METRICS.map((m) => (
                <th
                  key={m.key}
                  className="text-center px-3 py-2 text-[10px] font-semibold text-muted-foreground uppercase tracking-wider min-w-[110px]"
                >
                  {m.label}
                </th>
              ))}
              {/* Confidence column */}
              <th className="text-center px-3 py-2 text-[10px] font-semibold text-muted-foreground uppercase tracking-wider min-w-[80px]">
                Conf.
              </th>
              {/* Trend column */}
              <th className="text-center px-3 py-2 text-[10px] font-semibold text-muted-foreground uppercase tracking-wider min-w-[64px]">
                Trend
              </th>
            </tr>
          </thead>
          <tbody>
            {channels.map((ch) => {
              const Logo = getPlatformLogo(ch.platform);
              return (
                <tr
                  key={ch.channelId}
                  className={cn(
                    'border-b border-border/50 hover:bg-muted/20 transition-colors',
                    ch.isWinner && 'ring-1 ring-inset ring-emerald-500/20',
                  )}
                >
                  {/* Channel label */}
                  <td className="px-3 py-2.5 sticky left-0 bg-card z-10">
                    <div className="flex items-center gap-2">
                      <div
                        className="w-2 h-2 rounded-full flex-shrink-0"
                        style={{ backgroundColor: ch.color }}
                      />
                      <Logo size={16} className="flex-shrink-0 opacity-80" />
                      <span className="text-xs font-medium text-foreground whitespace-nowrap">
                        {ch.channelName}
                      </span>
                      {ch.isWinner && (
                        <svg
                          width="12"
                          height="12"
                          viewBox="0 0 16 16"
                          fill="none"
                          className="text-emerald-400 flex-shrink-0"
                        >
                          <path
                            d="M8 1l2.1 4.3 4.7.7-3.4 3.3.8 4.7L8 11.8 3.8 14l.8-4.7L1.2 6l4.7-.7L8 1z"
                            fill="currentColor"
                          />
                        </svg>
                      )}
                    </div>
                  </td>

                  {/* Metric cells */}
                  {METRICS.map((m) => {
                    const value = m.getValue(ch);
                    const delta = m.getDelta(ch);
                    const direction = m.getDirection(ch);
                    const rank = rankMaps[m.key]?.[ch.channelId] ?? 0;
                    const bgClass = heatmapClass(rank, channels.length);

                    return (
                      <td
                        key={m.key}
                        className={cn(
                          'px-3 py-2.5 text-center',
                          bgClass,
                        )}
                      >
                        <div className="font-mono text-xs font-semibold text-foreground">
                          {value}
                        </div>
                        {delta && (
                          <div
                            className={cn(
                              'text-[10px] font-mono mt-0.5',
                              direction === 'above'
                                ? 'text-emerald-400'
                                : direction === 'below'
                                  ? 'text-red-400'
                                  : 'text-muted-foreground',
                            )}
                          >
                            {delta}
                          </div>
                        )}
                      </td>
                    );
                  })}

                  {/* Confidence */}
                  <td className="px-3 py-2.5 text-center">
                    <ConfidencePip tier={ch.confidence} margin={ch.confidenceRange.margin} />
                  </td>

                  {/* Trend sparkline */}
                  <td className="px-3 py-2.5 text-center">
                    <TrendMini data={ch.trendData} color={ch.color} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Discrepancy Row */}
      <DiscrepancyRow channels={channels} />
    </div>
  );
};
