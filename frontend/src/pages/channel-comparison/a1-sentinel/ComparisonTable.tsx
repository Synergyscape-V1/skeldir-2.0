/**
 * ComparisonTable — A1-SENTINEL Primary Element
 *
 * Dense, spreadsheet-derived data grid with:
 * - Frozen metric labels on the left
 * - Channel columns with inline sparklines + confidence bars
 * - Discrepancy row with severity coloring
 * - Bloomberg Terminal density aesthetic
 */

import React, { useState } from 'react';
import { cn } from '@/lib/utils';
import { getPlatformLogo } from '@/pages/channel-comparison/shared/platform-logos';
import type {
  ChannelComparisonEntry,
  ConfidenceTier,
} from '@/pages/channel-comparison/shared/types';
import { ComparisonPulseBar } from './ComparisonPulseBar';
import { TrendSparkline } from './TrendSparkline';

interface ComparisonTableProps {
  channels: ChannelComparisonEntry[];
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

const ConfidenceBadge: React.FC<{ tier: ConfidenceTier; margin: number }> = ({ tier, margin }) => {
  const styles: Record<ConfidenceTier, string> = {
    high: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    medium: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    low: 'bg-red-500/10 text-red-400 border-red-500/20',
  };
  const labels: Record<ConfidenceTier, string> = {
    high: 'High Confidence',
    medium: 'Medium Confidence',
    low: 'Low Confidence',
  };
  return (
    <span className={cn('inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono border', styles[tier])}>
      {tier === 'high' ? (
        <svg width="8" height="8" viewBox="0 0 16 16" fill="currentColor"><path d="M8 1a7 7 0 110 14A7 7 0 018 1zm3.2 4.8L7 10l-2.2-2.2" stroke="currentColor" strokeWidth="2" fill="none"/></svg>
      ) : (
        <svg width="8" height="8" viewBox="0 0 16 16" fill="currentColor"><path d="M8 1a7 7 0 110 14A7 7 0 018 1zM7 4v5h2V4H7zm0 6v2h2v-2H7z" /></svg>
      )}
      {labels[tier]} · ±{margin}%
    </span>
  );
};

const DirectionArrow: React.FC<{ direction: 'above' | 'below' | 'at' }> = ({ direction }) => {
  if (direction === 'above') return <span className="text-emerald-400">&#9650;</span>;
  if (direction === 'below') return <span className="text-red-400">&#9660;</span>;
  return <span className="text-muted-foreground">&#8212;</span>;
};

const DiscrepancySeverity: React.FC<{ percent: number }> = ({ percent }) => {
  const abs = Math.abs(percent);
  const severity =
    abs < 5 ? 'text-emerald-400 bg-emerald-500/10' :
    abs < 15 ? 'text-amber-400 bg-amber-500/10' :
    'text-red-400 bg-red-500/10';
  const label =
    abs < 5 ? 'Aligned' :
    abs < 15 ? 'Review' :
    'Investigate';
  return (
    <span className={cn('inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono', severity)}>
      {percent > 0 ? '+' : ''}{percent.toFixed(1)}% · {label}
    </span>
  );
};

// ---------------------------------------------------------------------------
// Metric rows configuration
// ---------------------------------------------------------------------------

interface MetricDef {
  key: string;
  label: string;
  getValue: (ch: ChannelComparisonEntry) => string;
  getDelta: (ch: ChannelComparisonEntry) => string;
  getDirection: (ch: ChannelComparisonEntry) => 'above' | 'below' | 'at';
  hasConfidenceBar?: boolean;
}

const METRICS: MetricDef[] = [
  {
    key: 'revenue',
    label: 'Verified Revenue',
    getValue: (ch) => ch.verifiedRevenue,
    getDelta: (ch) => ch.revenueVsAverage,
    getDirection: (ch) => ch.revenueDirection,
  },
  {
    key: 'roas',
    label: 'ROAS',
    getValue: (ch) => ch.roas,
    getDelta: (ch) => ch.roasVsAverage,
    getDirection: (ch) => ch.roasDirection,
    hasConfidenceBar: true,
  },
  {
    key: 'spend',
    label: 'Ad Spend',
    getValue: (ch) => ch.adSpend,
    getDelta: () => '',
    getDirection: () => 'at',
  },
  {
    key: 'cpa',
    label: 'CPA',
    getValue: (ch) => ch.cpa,
    getDelta: () => '',
    getDirection: () => 'at',
  },
  {
    key: 'conversions',
    label: 'Conversions',
    getValue: (ch) => ch.conversions,
    getDelta: () => '',
    getDirection: () => 'at',
  },
];

// ---------------------------------------------------------------------------
// Main table
// ---------------------------------------------------------------------------

export const ComparisonTable: React.FC<ComparisonTableProps> = ({ channels }) => {
  const [expandedMetric, setExpandedMetric] = useState<string | null>(null);

  return (
    <div className="w-full overflow-x-auto rounded-lg border border-border bg-card">
      <table className="w-full border-collapse text-sm">
        {/* ---- HEADER: Channel columns ---- */}
        <thead>
          <tr className="border-b border-border">
            <th className="sticky left-0 z-10 bg-card px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground w-36">
              Metric
            </th>
            {channels.map((ch) => {
              const Logo = getPlatformLogo(ch.platform);
              return (
                <th key={ch.channelId} className="px-4 py-3 text-center min-w-[200px]">
                  <div className="flex flex-col items-center gap-1.5">
                    <div className="flex items-center gap-2">
                      <Logo size={16} />
                      <span className="font-semibold text-foreground text-xs">
                        {ch.channelName}
                      </span>
                      {ch.isWinner && (
                        <span className="px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-400 text-[9px] font-mono font-semibold uppercase tracking-widest border border-emerald-500/20">
                          Winner
                        </span>
                      )}
                    </div>
                    <ConfidenceBadge tier={ch.confidence} margin={ch.confidenceRange.margin} />
                  </div>
                </th>
              );
            })}
          </tr>
        </thead>

        <tbody>
          {/* ---- METRIC ROWS ---- */}
          {METRICS.map((metric) => (
            <React.Fragment key={metric.key}>
              <tr className="border-b border-border/50 hover:bg-muted/30 transition-colors duration-150">
                <td className="sticky left-0 z-10 bg-card px-4 py-2.5 text-xs font-medium text-muted-foreground w-36">
                  <div className="flex items-center gap-1">
                    {metric.label}
                    {metric.hasConfidenceBar && (
                      <button
                        onClick={() => setExpandedMetric(expandedMetric === metric.key ? null : metric.key)}
                        className="text-primary/60 hover:text-primary transition-colors ml-1"
                        aria-label={`Why this range for ${metric.label}?`}
                      >
                        <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                          <circle cx="8" cy="8" r="6.5" />
                          <path d="M6.5 6.5a1.5 1.5 0 113 0c0 .83-.67 1.17-1 1.5-.33.33-.5.67-.5 1m0 1.5h.01" strokeLinecap="round" />
                        </svg>
                      </button>
                    )}
                  </div>
                </td>
                {channels.map((ch) => (
                  <td key={ch.channelId} className="px-4 py-2.5 text-center">
                    <div className="flex flex-col items-center gap-1">
                      {/* Primary value */}
                      <span className={cn(
                        'font-mono text-sm font-semibold tabular-nums',
                        ch.isWinner && metric.key === 'roas' ? 'text-emerald-400' : 'text-foreground'
                      )}>
                        {metric.getValue(ch)}
                      </span>

                      {/* Delta vs average */}
                      {metric.getDelta(ch) && (
                        <span className="flex items-center gap-0.5 text-[10px] font-mono text-muted-foreground">
                          <DirectionArrow direction={metric.getDirection(ch)} />
                          {metric.getDelta(ch)}
                        </span>
                      )}

                      {/* Inline confidence bar for ROAS */}
                      {metric.hasConfidenceBar && (
                        <ComparisonPulseBar
                          confidence={ch.confidence}
                          pointPosition={0.5}
                          lowerPosition={0.5 - ch.confidenceRange.margin / 100}
                          upperPosition={0.5 + ch.confidenceRange.margin / 100}
                          formatLow={ch.confidenceRange.low}
                          formatHigh={ch.confidenceRange.high}
                          width={140}
                          height={24}
                        />
                      )}
                    </div>
                  </td>
                ))}
              </tr>

              {/* Expandable explainability row */}
              {metric.hasConfidenceBar && expandedMetric === metric.key && (
                <tr className="border-b border-border/50 bg-muted/20">
                  <td className="sticky left-0 z-10 bg-muted/20 px-4 py-2 text-[10px] text-muted-foreground italic">
                    Why this range?
                  </td>
                  {channels.map((ch) => (
                    <td key={ch.channelId} className="px-4 py-2 text-[10px] text-muted-foreground text-center leading-relaxed">
                      {ch.confidenceExplanation}
                    </td>
                  ))}
                </tr>
              )}
            </React.Fragment>
          ))}

          {/* ---- TREND ROW ---- */}
          <tr className="border-b border-border/50 hover:bg-muted/30 transition-colors duration-150">
            <td className="sticky left-0 z-10 bg-card px-4 py-2.5 text-xs font-medium text-muted-foreground w-36">
              ROAS Trend
            </td>
            {channels.map((ch) => (
              <td key={ch.channelId} className="px-4 py-2.5">
                <div className="flex justify-center">
                  <TrendSparkline data={ch.trendData} trend={ch.trend} width={120} height={28} />
                </div>
              </td>
            ))}
          </tr>

          {/* ---- DISCREPANCY ROW ---- */}
          <tr className="border-b border-border/50 hover:bg-muted/30 transition-colors duration-150">
            <td className="sticky left-0 z-10 bg-card px-4 py-2.5 text-xs font-medium text-muted-foreground w-36">
              Revenue Verification
            </td>
            {channels.map((ch) => (
              <td key={ch.channelId} className="px-4 py-2.5 text-center">
                <div className="flex flex-col items-center gap-1">
                  <div className="flex items-center gap-2 text-[10px] font-mono text-muted-foreground">
                    <span>Claimed: {ch.platformClaimed}</span>
                    <span className="text-foreground/30">|</span>
                    <span>Verified: {ch.verified}</span>
                  </div>
                  <DiscrepancySeverity percent={ch.discrepancyPercent} />
                </div>
              </td>
            ))}
          </tr>
        </tbody>
      </table>
    </div>
  );
};
