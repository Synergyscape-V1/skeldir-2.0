/**
 * ChannelBriefCard — Per-channel narrative summary card
 *
 * Part of A2-MERIDIAN's "executive brief" layout.
 * Each card presents a single channel as a readable brief:
 *   - Platform logo + name + confidence badge
 *   - Key metrics: Revenue, ROAS, CPA (with vs-average deltas)
 *   - Mini trend sparkline
 *   - Discrepancy signal
 *   - "Why this range?" expandable explanation
 *
 * Design: spacious, McKinsey-slide aesthetic. Not a table row.
 */

import React, { useState } from 'react';
import { cn } from '@/lib/utils';
import type {
  ChannelComparisonEntry,
  ConfidenceTier,
  TrendDirection,
} from '@/pages/channel-comparison/shared/types';
import { getPlatformLogo } from '@/pages/channel-comparison/shared/platform-logos';

// ---------------------------------------------------------------------------
// Confidence styles
// ---------------------------------------------------------------------------

const CONFIDENCE_STYLES: Record<ConfidenceTier, { badge: string; label: string }> = {
  high: {
    badge: 'bg-emerald-400/10 text-emerald-400 border-emerald-400/20',
    label: 'High Confidence',
  },
  medium: {
    badge: 'bg-amber-400/10 text-amber-400 border-amber-400/20',
    label: 'Medium Confidence',
  },
  low: {
    badge: 'bg-red-400/10 text-red-400 border-red-400/20',
    label: 'Low Confidence',
  },
};

const TREND_CONFIG: Record<TrendDirection, { icon: string; label: string; color: string }> = {
  up: { icon: '\u2191', label: 'Trending up', color: 'text-emerald-400' },
  down: { icon: '\u2193', label: 'Trending down', color: 'text-red-400' },
  stable: { icon: '\u2192', label: 'Stable', color: 'text-muted-foreground' },
};

// ---------------------------------------------------------------------------
// Mini Sparkline
// ---------------------------------------------------------------------------

const MiniSparkline: React.FC<{
  data: ChannelComparisonEntry['trendData'];
  trend: TrendDirection;
}> = ({ data, trend }) => {
  if (data.length === 0) return null;

  const width = 120;
  const height = 32;
  const padding = 2;

  const values = data.map((d) => d.roas);
  const min = Math.min(...values, ...data.map((d) => d.roasLow));
  const max = Math.max(...values, ...data.map((d) => d.roasHigh));
  const range = max - min || 1;

  const toX = (i: number) => padding + (i / (data.length - 1)) * (width - 2 * padding);
  const toY = (v: number) => height - padding - ((v - min) / range) * (height - 2 * padding);

  // Main line
  const linePath = data
    .map((d, i) => `${i === 0 ? 'M' : 'L'}${toX(i).toFixed(1)},${toY(d.roas).toFixed(1)}`)
    .join(' ');

  // Confidence band
  const bandUpper = data.map((d, i) => `${i === 0 ? 'M' : 'L'}${toX(i).toFixed(1)},${toY(d.roasHigh).toFixed(1)}`).join(' ');
  const bandLower = [...data].reverse().map((d, i) => `L${toX(data.length - 1 - i).toFixed(1)},${toY(d.roasLow).toFixed(1)}`).join(' ');
  const bandPath = `${bandUpper} ${bandLower} Z`;

  const strokeColor =
    trend === 'up' ? '#34d399' : trend === 'down' ? '#f87171' : '#94a3b8';
  const fillColor =
    trend === 'up' ? '#34d39915' : trend === 'down' ? '#f8717115' : '#94a3b815';

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className="flex-shrink-0"
      aria-label={`Trend sparkline: ${TREND_CONFIG[trend].label}`}
      role="img"
    >
      {/* Confidence band */}
      <path d={bandPath} fill={fillColor} />
      {/* Main line */}
      <path d={linePath} fill="none" stroke={strokeColor} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      {/* End dot */}
      <circle
        cx={toX(data.length - 1)}
        cy={toY(data[data.length - 1].roas)}
        r="2.5"
        fill={strokeColor}
      />
    </svg>
  );
};

// ---------------------------------------------------------------------------
// Metric Row
// ---------------------------------------------------------------------------

const MetricRow: React.FC<{
  label: string;
  value: string;
  delta?: string;
  direction?: 'above' | 'below' | 'at';
}> = ({ label, value, delta, direction }) => (
  <div className="flex items-baseline justify-between py-1.5">
    <span className="text-xs text-muted-foreground">{label}</span>
    <div className="flex items-baseline gap-2">
      <span className="text-sm font-mono font-semibold text-foreground">{value}</span>
      {delta && (
        <span
          className={cn(
            'text-[10px] font-mono',
            direction === 'above' && 'text-emerald-400',
            direction === 'below' && 'text-red-400',
            direction === 'at' && 'text-muted-foreground',
          )}
        >
          {delta}
        </span>
      )}
    </div>
  </div>
);

// ---------------------------------------------------------------------------
// Discrepancy Signal
// ---------------------------------------------------------------------------

const DiscrepancySignal: React.FC<{
  platformClaimed: string;
  verified: string;
  discrepancyPercent: number;
}> = ({ platformClaimed, verified, discrepancyPercent }) => {
  const severity =
    discrepancyPercent >= 20 ? 'high' : discrepancyPercent >= 10 ? 'medium' : 'low';

  return (
    <div
      className={cn(
        'flex items-center gap-2 px-3 py-2 rounded-md text-[11px]',
        severity === 'high' && 'bg-red-400/5 border border-red-400/15',
        severity === 'medium' && 'bg-amber-400/5 border border-amber-400/15',
        severity === 'low' && 'bg-muted/50 border border-border',
      )}
    >
      <svg
        width="14"
        height="14"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        className={cn(
          severity === 'high' && 'text-red-400',
          severity === 'medium' && 'text-amber-400',
          severity === 'low' && 'text-muted-foreground',
        )}
      >
        <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
        <line x1="12" y1="9" x2="12" y2="13" />
        <line x1="12" y1="17" x2="12.01" y2="17" />
      </svg>
      <div className="flex-1 min-w-0">
        <span className="text-muted-foreground">
          Platform reported {platformClaimed}, verified at {verified}
        </span>
        <span
          className={cn(
            'font-mono font-medium ml-1.5',
            severity === 'high' && 'text-red-400',
            severity === 'medium' && 'text-amber-400',
            severity === 'low' && 'text-muted-foreground',
          )}
        >
          ({discrepancyPercent.toFixed(1)}% gap)
        </span>
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export interface ChannelBriefCardProps {
  channel: ChannelComparisonEntry;
  className?: string;
}

export const ChannelBriefCard: React.FC<ChannelBriefCardProps> = ({
  channel,
  className,
}) => {
  const [whyExpanded, setWhyExpanded] = useState(false);

  const Logo = getPlatformLogo(channel.platform);
  const confidenceStyle = CONFIDENCE_STYLES[channel.confidence];
  const trendConfig = TREND_CONFIG[channel.trend];

  return (
    <article
      className={cn(
        'rounded-xl border bg-card p-5 transition-shadow hover:shadow-md',
        channel.isWinner
          ? 'border-emerald-400/30 shadow-sm shadow-emerald-400/5'
          : 'border-border',
        className,
      )}
    >
      {/* Header: Logo + Name + Winner + Confidence + Trend */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div
            className="w-9 h-9 rounded-lg flex items-center justify-center"
            style={{ backgroundColor: `${channel.color}15` }}
          >
            <Logo size={20} className="text-foreground" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold text-foreground">
                {channel.channelName}
              </h3>
              {channel.isWinner && (
                <span className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-400/10 text-emerald-400">
                  <svg width="10" height="10" viewBox="0 0 16 16" fill="currentColor">
                    <path d="M8 1l2.1 4.3 4.7.7-3.4 3.3.8 4.7L8 11.8 3.8 14l.8-4.7L1.2 6l4.7-.7L8 1z" />
                  </svg>
                  Leader
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 mt-0.5">
              <span
                className={cn(
                  'px-1.5 py-0.5 rounded border text-[10px] font-mono',
                  confidenceStyle.badge,
                )}
              >
                {confidenceStyle.label}
              </span>
              <span
                className={cn(
                  'text-[11px] font-medium flex items-center gap-0.5',
                  trendConfig.color,
                )}
              >
                <span aria-hidden="true">{trendConfig.icon}</span>
                {trendConfig.label}
              </span>
            </div>
          </div>
        </div>

        {/* Mini sparkline */}
        <MiniSparkline data={channel.trendData} trend={channel.trend} />
      </div>

      {/* Metrics */}
      <div className="border-t border-border/60 pt-3 space-y-0.5">
        <MetricRow
          label="Verified Revenue"
          value={channel.verifiedRevenue}
          delta={channel.revenueVsAverage}
          direction={channel.revenueDirection}
        />
        <MetricRow
          label="ROAS"
          value={channel.roas}
          delta={channel.roasVsAverage}
          direction={channel.roasDirection}
        />
        <MetricRow label="Ad Spend" value={channel.adSpend} />
        <MetricRow label="CPA" value={channel.cpa} />
        <MetricRow label="Conversions" value={channel.conversions} />
      </div>

      {/* Confidence range */}
      <div className="mt-3 flex items-center gap-2 text-[10px] font-mono text-muted-foreground">
        <span>Range: {channel.confidenceRange.low} \u2013 {channel.confidenceRange.high}</span>
        <span className="text-muted-foreground/40">\u00b7</span>
        <span>\u00b1{channel.confidenceRange.margin}%</span>
      </div>

      {/* Discrepancy */}
      <div className="mt-3">
        <DiscrepancySignal
          platformClaimed={channel.platformClaimed}
          verified={channel.verified}
          discrepancyPercent={channel.discrepancyPercent}
        />
      </div>

      {/* "Why this range?" expandable */}
      <div className="mt-3">
        <button
          onClick={() => setWhyExpanded((prev) => !prev)}
          className="flex items-center gap-1.5 text-[11px] font-medium text-primary hover:text-primary/80 transition-colors"
          aria-expanded={whyExpanded}
        >
          <svg
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            className={cn(
              'transition-transform duration-200',
              whyExpanded && 'rotate-90',
            )}
          >
            <path d="M9 18l6-6-6-6" />
          </svg>
          Why this range?
        </button>
        {whyExpanded && (
          <p className="mt-2 pl-5 text-[11px] text-muted-foreground leading-relaxed">
            {channel.confidenceExplanation}
          </p>
        )}
      </div>
    </article>
  );
};
