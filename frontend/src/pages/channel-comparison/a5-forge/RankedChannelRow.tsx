/**
 * RankedChannelRow — Single channel in the ranked list
 *
 * Collapsed: rank + platform logo + name + ROAS + confidence badge + RankShiftIndicator + chevron
 * Expanded: full metrics grid, confidence range, trend sparkline, verification, winner explanation
 *
 * Design aesthetic: "forensic ranking" — authoritative, evidence-based.
 * #1 rank gets prominent left border accent and larger text.
 */

import React from 'react';
import { cn } from '@/lib/utils';
import type { ChannelComparisonEntry, ConfidenceTier } from '@/pages/channel-comparison/shared/types';
import { getPlatformLogo } from '@/pages/channel-comparison/shared/platform-logos';
import { RankShiftIndicator } from './RankShiftIndicator';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface RankedChannelRowProps {
  rank: number;
  channel: ChannelComparisonEntry;
  isExpanded: boolean;
  onToggle: () => void;
}

// ---------------------------------------------------------------------------
// Confidence badge styles
// ---------------------------------------------------------------------------

const CONFIDENCE_STYLES: Record<ConfidenceTier, string> = {
  high: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  medium: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  low: 'bg-red-500/10 text-red-400 border-red-500/20',
};

const CONFIDENCE_LABELS: Record<ConfidenceTier, string> = {
  high: 'High',
  medium: 'Medium',
  low: 'Low',
};

// ---------------------------------------------------------------------------
// Mini Trend Sparkline (inline SVG)
// ---------------------------------------------------------------------------

const TrendSparkline: React.FC<{ data: ChannelComparisonEntry['trendData'] }> = ({ data }) => {
  if (!data.length) return null;

  const width = 200;
  const height = 48;
  const padding = { top: 6, bottom: 6, left: 4, right: 4 };

  const allValues = data.flatMap((d) => [d.roasLow, d.roasHigh]);
  const minVal = Math.min(...allValues);
  const maxVal = Math.max(...allValues);
  const range = maxVal - minVal || 1;

  const xScale = (i: number) =>
    padding.left + (i / (data.length - 1)) * (width - padding.left - padding.right);
  const yScale = (v: number) =>
    padding.top + (1 - (v - minVal) / range) * (height - padding.top - padding.bottom);

  // Confidence band polygon
  const bandPoints = [
    ...data.map((d, i) => `${xScale(i)},${yScale(d.roasHigh)}`),
    ...data.slice().reverse().map((d, i) => `${xScale(data.length - 1 - i)},${yScale(d.roasLow)}`),
  ].join(' ');

  // Main line
  const linePath = data.map((d, i) => `${i === 0 ? 'M' : 'L'}${xScale(i)},${yScale(d.roas)}`).join(' ');

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className="block"
      aria-label="ROAS trend over selected date range"
      role="img"
    >
      {/* Confidence band */}
      <polygon points={bandPoints} fill="currentColor" className="text-primary/10" />
      {/* Main ROAS line */}
      <path d={linePath} fill="none" stroke="currentColor" strokeWidth="1.5" className="text-primary" />
      {/* Latest point */}
      <circle
        cx={xScale(data.length - 1)}
        cy={yScale(data[data.length - 1].roas)}
        r="2.5"
        fill="currentColor"
        className="text-primary"
      />
    </svg>
  );
};

// ---------------------------------------------------------------------------
// Metric cell helper
// ---------------------------------------------------------------------------

const MetricCell: React.FC<{
  label: string;
  value: string;
  delta?: string;
  direction?: 'above' | 'below' | 'at';
}> = ({ label, value, delta, direction }) => (
  <div className="flex flex-col gap-0.5">
    <span className="text-[10px] uppercase tracking-wider text-muted-foreground/70 font-medium">
      {label}
    </span>
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
);

// ---------------------------------------------------------------------------
// Discrepancy bar
// ---------------------------------------------------------------------------

const DiscrepancyBar: React.FC<{
  claimed: string;
  verified: string;
  discrepancyPercent: number;
}> = ({ claimed, verified, discrepancyPercent }) => {
  const severity =
    discrepancyPercent > 20 ? 'text-red-400' : discrepancyPercent > 10 ? 'text-amber-400' : 'text-emerald-400';
  const barWidth = Math.min(discrepancyPercent, 100);

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-[10px] text-muted-foreground">
        <span>
          Platform claimed: <span className="font-mono text-foreground">{claimed}</span>
        </span>
        <span>
          Verified: <span className="font-mono text-foreground">{verified}</span>
        </span>
      </div>
      <div className="h-1.5 rounded-full bg-muted overflow-hidden">
        <div
          className={cn('h-full rounded-full transition-all', severity.replace('text-', 'bg-'))}
          style={{ width: `${barWidth}%` }}
        />
      </div>
      <div className={cn('text-[10px] font-mono font-medium', severity)}>
        {discrepancyPercent}% discrepancy
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export const RankedChannelRow: React.FC<RankedChannelRowProps> = ({
  rank,
  channel,
  isExpanded,
  onToggle,
}) => {
  const isWinner = rank === 1;
  const PlatformLogo = getPlatformLogo(channel.platform);

  return (
    <div
      className={cn(
        'rounded-lg border transition-all duration-200',
        isWinner
          ? 'border-emerald-500/30 bg-card shadow-sm shadow-emerald-500/5'
          : 'border-border bg-card',
        isExpanded && 'ring-1 ring-primary/20',
      )}
    >
      {/* ---- COLLAPSED ROW ---- */}
      <button
        onClick={onToggle}
        className={cn(
          'w-full flex items-center gap-3 px-4 py-3 text-left transition-colors',
          'hover:bg-muted/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 rounded-lg',
        )}
        aria-expanded={isExpanded}
        aria-controls={`drawer-${channel.channelId}`}
      >
        {/* Rank number */}
        <div
          className={cn(
            'flex-shrink-0 flex items-center justify-center rounded font-mono font-bold',
            isWinner
              ? 'w-10 h-10 text-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
              : 'w-8 h-8 text-sm bg-muted text-muted-foreground',
          )}
        >
          {rank}
        </div>

        {/* Platform logo + channel name */}
        <div className="flex items-center gap-2.5 min-w-0 flex-1">
          <PlatformLogo size={isWinner ? 22 : 18} />
          <span
            className={cn(
              'font-semibold truncate',
              isWinner ? 'text-base text-foreground' : 'text-sm text-foreground',
            )}
          >
            {channel.channelName}
          </span>
          {channel.isWinner && (
            <span className="flex-shrink-0 px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              Winner
            </span>
          )}
        </div>

        {/* ROAS value — large and prominent */}
        <div className="flex-shrink-0 text-right mr-2">
          <div
            className={cn(
              'font-mono font-bold',
              isWinner ? 'text-xl text-emerald-400' : 'text-base text-foreground',
            )}
          >
            {channel.roas}
          </div>
          <div className="text-[10px] text-muted-foreground/70 uppercase tracking-wider">
            ROAS
          </div>
        </div>

        {/* Confidence badge */}
        <span
          className={cn(
            'flex-shrink-0 px-2 py-0.5 rounded text-[10px] font-mono font-medium border',
            CONFIDENCE_STYLES[channel.confidence],
          )}
        >
          {CONFIDENCE_LABELS[channel.confidence]}
        </span>

        {/* Rank shift indicator */}
        <RankShiftIndicator trend={channel.trend} size={20} className="flex-shrink-0" />

        {/* Expand chevron */}
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className={cn(
            'flex-shrink-0 text-muted-foreground transition-transform duration-200',
            isExpanded && 'rotate-180',
          )}
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>

      {/* ---- EXPANDED DRAWER ---- */}
      {isExpanded && (
        <div
          id={`drawer-${channel.channelId}`}
          className="border-t border-border/50 px-6 py-5 space-y-5 animate-in slide-in-from-top-1 duration-200"
        >
          {/* Metrics grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <MetricCell
              label="Verified Revenue"
              value={channel.verifiedRevenue}
              delta={channel.revenueVsAverage}
              direction={channel.revenueDirection}
            />
            <MetricCell
              label="Ad Spend"
              value={channel.adSpend}
            />
            <MetricCell
              label="CPA"
              value={channel.cpa}
            />
            <MetricCell
              label="Conversions"
              value={channel.conversions}
            />
          </div>

          {/* ROAS vs average */}
          <div className="flex items-center gap-3 px-3 py-2 rounded bg-muted/30 border border-border/50">
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground/70 font-medium">
              ROAS vs Average
            </span>
            <span
              className={cn(
                'text-sm font-mono font-semibold',
                channel.roasDirection === 'above' && 'text-emerald-400',
                channel.roasDirection === 'below' && 'text-red-400',
                channel.roasDirection === 'at' && 'text-muted-foreground',
              )}
            >
              {channel.roasVsAverage}
            </span>
          </div>

          {/* Two-column: Confidence + Trend */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {/* Confidence range + explanation */}
            <div className="space-y-2">
              <h4 className="text-[10px] uppercase tracking-wider text-muted-foreground/70 font-semibold">
                Confidence Range
              </h4>
              <div className="flex items-center gap-2">
                <span
                  className={cn(
                    'px-2 py-0.5 rounded text-xs font-mono border',
                    CONFIDENCE_STYLES[channel.confidence],
                  )}
                >
                  {channel.confidenceRange.low} &mdash; {channel.confidenceRange.high}
                </span>
                <span className="text-[10px] font-mono text-muted-foreground">
                  &pm;{channel.confidenceRange.margin}%
                </span>
              </div>
              {/* "Why this range?" */}
              <div className="rounded bg-muted/20 border border-border/30 px-3 py-2">
                <span className="text-[10px] font-semibold text-muted-foreground block mb-0.5">
                  Why this range?
                </span>
                <p className="text-[11px] text-muted-foreground/80 leading-relaxed">
                  {channel.confidenceExplanation}
                </p>
              </div>
            </div>

            {/* Trend sparkline */}
            <div className="space-y-2">
              <h4 className="text-[10px] uppercase tracking-wider text-muted-foreground/70 font-semibold">
                ROAS Trend
              </h4>
              <div className="rounded bg-muted/20 border border-border/30 p-2">
                <TrendSparkline data={channel.trendData} />
              </div>
              <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground/60">
                <div className="w-3 h-px bg-primary" />
                <span>ROAS</span>
                <div className="w-3 h-2 bg-primary/10 rounded-sm ml-2" />
                <span>Confidence band</span>
              </div>
            </div>
          </div>

          {/* Revenue verification / discrepancy */}
          <div className="space-y-2">
            <h4 className="text-[10px] uppercase tracking-wider text-muted-foreground/70 font-semibold">
              Revenue Verification
            </h4>
            <DiscrepancyBar
              claimed={channel.platformClaimed}
              verified={channel.verified}
              discrepancyPercent={channel.discrepancyPercent}
            />
          </div>

          {/* Winner explanation (if applicable) */}
          {channel.isWinner && channel.winnerExplanation && (
            <div className="flex items-start gap-2.5 px-3 py-2.5 rounded-lg bg-emerald-500/5 border border-emerald-500/15">
              <svg
                width="14"
                height="14"
                viewBox="0 0 16 16"
                fill="none"
                className="text-emerald-400 flex-shrink-0 mt-0.5"
              >
                <path
                  d="M8 1l2.1 4.3 4.7.7-3.4 3.3.8 4.7L8 11.8 3.8 14l.8-4.7L1.2 6l4.7-.7L8 1z"
                  fill="currentColor"
                />
              </svg>
              <div>
                <span className="text-[10px] font-semibold text-emerald-400 block">
                  Why #{rank}?
                </span>
                <p className="text-[11px] text-muted-foreground/80 leading-relaxed">
                  {channel.winnerExplanation}
                </p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
