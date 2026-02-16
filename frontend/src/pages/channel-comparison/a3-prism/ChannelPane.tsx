/**
 * ChannelPane — Single channel's vertical card stack
 *
 * Renders a full mini-dashboard for one channel inside A3-PRISM's
 * split-pane grid. Contains:
 *   - PaneHeader (logo + name + heartbeat + winner badge)
 *   - MetricCard rows (Revenue, ROAS, Ad Spend, CPA, Conversions)
 *   - TrendSection (inline sparkline)
 *   - VerificationSection (claimed vs verified + discrepancy)
 *   - ExplainabilitySection ("Why this range?" expandable)
 *
 * @module A3-PRISM / ChannelPane
 */

import React, { useState, useMemo } from 'react';
import { cn } from '@/lib/utils';
import { getPlatformLogo } from '@/pages/channel-comparison/shared/platform-logos';
import type {
  ChannelComparisonEntry,
  ConfidenceTier,
  TrendDirection,
} from '@/pages/channel-comparison/shared/types';
import { HealthHeartbeat } from './HealthHeartbeat';

// ---------------------------------------------------------------------------
// Sub-component: MetricCard
// ---------------------------------------------------------------------------

interface MetricCardProps {
  label: string;
  value: string;
  delta?: string;
  direction?: 'above' | 'below' | 'at';
  confidence?: { tier: ConfidenceTier; low: string; high: string; margin: number };
}

const CONFIDENCE_COLORS: Record<ConfidenceTier, string> = {
  high: 'bg-emerald-500',
  medium: 'bg-amber-500',
  low: 'bg-red-500',
};

const CONFIDENCE_TRACK_COLORS: Record<ConfidenceTier, string> = {
  high: 'bg-emerald-500/20',
  medium: 'bg-amber-500/20',
  low: 'bg-red-500/20',
};

const MetricCard: React.FC<MetricCardProps> = ({
  label,
  value,
  delta,
  direction,
  confidence,
}) => (
  <div className="rounded-md border border-border bg-card px-3 py-2.5">
    <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
      {label}
    </p>
    <p className="mt-0.5 font-mono text-lg font-semibold text-foreground">
      {value}
    </p>
    {delta && (
      <p
        className={cn(
          'mt-0.5 font-mono text-xs',
          direction === 'above' && 'text-emerald-500',
          direction === 'below' && 'text-red-400',
          direction === 'at' && 'text-muted-foreground',
        )}
      >
        {delta}
      </p>
    )}
    {confidence && (
      <div className="mt-2">
        <div className="flex items-center justify-between text-[10px] text-muted-foreground">
          <span>{confidence.low}</span>
          <span className="capitalize">{confidence.tier} &middot; &plusmn;{confidence.margin}%</span>
          <span>{confidence.high}</span>
        </div>
        <div
          className={cn(
            'mt-1 h-1.5 w-full overflow-hidden rounded-full',
            CONFIDENCE_TRACK_COLORS[confidence.tier],
          )}
        >
          <div
            className={cn(
              'h-full rounded-full transition-all duration-500',
              CONFIDENCE_COLORS[confidence.tier],
            )}
            style={{
              width: `${Math.max(10, 100 - confidence.margin)}%`,
            }}
          />
        </div>
      </div>
    )}
  </div>
);

// ---------------------------------------------------------------------------
// Sub-component: TrendSection
// ---------------------------------------------------------------------------

interface TrendSectionProps {
  trend: TrendDirection;
  trendData: ChannelComparisonEntry['trendData'];
}

const TREND_ICON: Record<TrendDirection, string> = {
  up: '\u25B2',    // ▲
  down: '\u25BC',  // ▼
  stable: '\u25C6', // ◆
};

const TREND_LABEL: Record<TrendDirection, string> = {
  up: 'Trending Up',
  down: 'Trending Down',
  stable: 'Stable',
};

const TREND_COLOR: Record<TrendDirection, string> = {
  up: 'text-emerald-500',
  down: 'text-red-400',
  stable: 'text-amber-500',
};

const TrendSection: React.FC<TrendSectionProps> = ({ trend, trendData }) => {
  // Build a simple SVG sparkline
  const sparkline = useMemo(() => {
    if (!trendData.length) return null;

    const width = 160;
    const height = 36;
    const padding = 2;

    const roasValues = trendData.map((d) => d.roas);
    const roasLow = trendData.map((d) => d.roasLow);
    const roasHigh = trendData.map((d) => d.roasHigh);

    const allValues = [...roasValues, ...roasLow, ...roasHigh];
    const min = Math.min(...allValues);
    const max = Math.max(...allValues);
    const range = max - min || 1;

    const xStep = (width - padding * 2) / Math.max(trendData.length - 1, 1);

    const toY = (v: number) =>
      height - padding - ((v - min) / range) * (height - padding * 2);

    const mainPath = roasValues
      .map((v, i) => `${i === 0 ? 'M' : 'L'}${padding + i * xStep},${toY(v)}`)
      .join(' ');

    // Confidence band as a closed polygon
    const bandTop = roasHigh
      .map((v, i) => `${padding + i * xStep},${toY(v)}`)
      .join(' ');
    const bandBottom = roasLow
      .map((v, i) => `${padding + (roasLow.length - 1 - i) * xStep},${toY(v)}`)
      .reverse()
      .join(' ');

    return { width, height, mainPath, bandTop, bandBottom };
  }, [trendData]);

  return (
    <div className="rounded-md border border-border bg-card px-3 py-2.5">
      <div className="flex items-center gap-1.5">
        <span className={cn('text-xs', TREND_COLOR[trend])}>{TREND_ICON[trend]}</span>
        <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
          {TREND_LABEL[trend]}
        </p>
      </div>
      {sparkline && (
        <svg
          width={sparkline.width}
          height={sparkline.height}
          viewBox={`0 0 ${sparkline.width} ${sparkline.height}`}
          className="mt-1.5 w-full"
          aria-label={`ROAS trend sparkline: ${trend}`}
          role="img"
        >
          {/* Confidence band */}
          <polygon
            points={`${sparkline.bandTop} ${sparkline.bandBottom}`}
            className="fill-primary/10"
          />
          {/* Main line */}
          <path
            d={sparkline.mainPath}
            fill="none"
            className="stroke-primary"
            strokeWidth={1.5}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Sub-component: VerificationSection
// ---------------------------------------------------------------------------

interface VerificationSectionProps {
  platformClaimed: string;
  verified: string;
  discrepancyPercent: number;
}

const VerificationSection: React.FC<VerificationSectionProps> = ({
  platformClaimed,
  verified,
  discrepancyPercent,
}) => {
  const severity =
    discrepancyPercent > 20
      ? 'text-red-400'
      : discrepancyPercent > 10
        ? 'text-amber-500'
        : 'text-emerald-500';

  return (
    <div className="rounded-md border border-border bg-card px-3 py-2.5">
      <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
        Verification
      </p>
      <div className="mt-1.5 space-y-1 text-xs">
        <div className="flex justify-between">
          <span className="text-muted-foreground">Platform claimed</span>
          <span className="font-mono text-foreground">{platformClaimed}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">Skeldir verified</span>
          <span className="font-mono text-foreground">{verified}</span>
        </div>
        <div className="flex justify-between border-t border-border pt-1">
          <span className="text-muted-foreground">Discrepancy</span>
          <span className={cn('font-mono font-semibold', severity)}>
            {discrepancyPercent.toFixed(1)}%
          </span>
        </div>
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Sub-component: ExplainabilitySection
// ---------------------------------------------------------------------------

interface ExplainabilitySectionProps {
  explanation: string;
}

const ExplainabilitySection: React.FC<ExplainabilitySectionProps> = ({
  explanation,
}) => {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-md border border-border bg-card px-3 py-2.5">
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="flex w-full items-center justify-between text-left"
        aria-expanded={expanded}
      >
        <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
          Why this range?
        </span>
        <span
          className={cn(
            'text-xs text-muted-foreground transition-transform duration-200',
            expanded && 'rotate-180',
          )}
        >
          &#9662;
        </span>
      </button>
      {expanded && (
        <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
          {explanation}
        </p>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Main: ChannelPane
// ---------------------------------------------------------------------------

export interface ChannelPaneProps {
  channel: ChannelComparisonEntry;
  lastUpdated: string;
}

export const ChannelPane: React.FC<ChannelPaneProps> = ({
  channel,
  lastUpdated,
}) => {
  const Logo = getPlatformLogo(channel.platform);

  return (
    <div
      className={cn(
        'flex flex-col gap-2 rounded-lg border bg-background p-3',
        channel.isWinner
          ? 'border-primary/50 shadow-[0_0_12px_-2px] shadow-primary/20'
          : 'border-border',
      )}
    >
      {/* Colored accent bar at top */}
      <div
        className="h-1 w-full rounded-full"
        style={{ backgroundColor: channel.color }}
      />

      {/* Pane Header */}
      <div className="flex items-center gap-2">
        <Logo size={20} className="shrink-0" />
        <h3 className="flex-1 truncate font-sans text-sm font-semibold text-foreground">
          {channel.channelName}
        </h3>
        <HealthHeartbeat lastUpdated={lastUpdated} size={10} />
        {channel.isWinner && (
          <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-semibold text-primary">
            <svg
              width="10"
              height="10"
              viewBox="0 0 20 20"
              fill="currentColor"
              aria-hidden="true"
            >
              <path d="M10 1l2.39 4.84 5.34.78-3.87 3.77.91 5.32L10 13.27l-4.77 2.44.91-5.32L2.27 6.62l5.34-.78L10 1z" />
            </svg>
            Winner
          </span>
        )}
      </div>

      {/* Metric Cards */}
      <MetricCard
        label="Verified Revenue"
        value={channel.verifiedRevenue}
        delta={channel.revenueVsAverage}
        direction={channel.revenueDirection}
        confidence={{
          tier: channel.confidence,
          low: channel.confidenceRange.low,
          high: channel.confidenceRange.high,
          margin: channel.confidenceRange.margin,
        }}
      />

      <MetricCard
        label="ROAS"
        value={channel.roas}
        delta={channel.roasVsAverage}
        direction={channel.roasDirection}
        confidence={{
          tier: channel.confidence,
          low: channel.confidenceRange.low,
          high: channel.confidenceRange.high,
          margin: channel.confidenceRange.margin,
        }}
      />

      <MetricCard label="Ad Spend" value={channel.adSpend} />

      <MetricCard label="CPA" value={channel.cpa} />

      <MetricCard label="Conversions" value={channel.conversions} />

      {/* Trend */}
      <TrendSection trend={channel.trend} trendData={channel.trendData} />

      {/* Verification */}
      <VerificationSection
        platformClaimed={channel.platformClaimed}
        verified={channel.verified}
        discrepancyPercent={channel.discrepancyPercent}
      />

      {/* Explainability */}
      <ExplainabilitySection explanation={channel.confidenceExplanation} />

      {/* Winner explanation (if applicable) */}
      {channel.isWinner && channel.winnerExplanation && (
        <div className="rounded-md border border-primary/30 bg-primary/5 px-3 py-2">
          <p className="text-[11px] font-medium uppercase tracking-wider text-primary">
            Winner Determination
          </p>
          <p className="mt-1 text-xs leading-relaxed text-foreground">
            {channel.winnerExplanation}
          </p>
        </div>
      )}
    </div>
  );
};

ChannelPane.displayName = 'ChannelPane';

export default ChannelPane;
