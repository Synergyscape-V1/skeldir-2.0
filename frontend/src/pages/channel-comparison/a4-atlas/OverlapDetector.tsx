/**
 * OverlapDetector — Animated SVG Confidence Interval Comparison
 *
 * The signature trust mechanism for A4-ATLAS. Shows all channels'
 * confidence intervals as stacked horizontal bars. When ranges
 * DON'T overlap (clear winner), a pulsing gap highlight appears.
 *
 * - Normalizes all ranges to a common pixel scale
 * - Respects `prefers-reduced-motion`
 * - Fully accessible with aria-label
 */

import React, { useMemo } from 'react';
import { cn } from '@/lib/utils';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface OverlapChannel {
  name: string;
  color: string;
  low: number;
  high: number;
  point: number;
}

export interface OverlapDetectorProps {
  channels: OverlapChannel[];
  className?: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SVG_WIDTH = 600;
const SVG_HEIGHT_PER_BAR = 32;
const BAR_HEIGHT = 14;
const LABEL_WIDTH = 100;
const CHART_LEFT = LABEL_WIDTH + 8;
const CHART_RIGHT = SVG_WIDTH - 16;
const CHART_WIDTH = CHART_RIGHT - CHART_LEFT;
const POINT_RADIUS = 4;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Find gaps where a channel's low is above another's high — indicating no overlap */
function findGaps(channels: OverlapChannel[]): Array<{ gapStart: number; gapEnd: number }> {
  if (channels.length < 2) return [];

  // Sort channels by their lower bound
  const sorted = [...channels].sort((a, b) => a.low - b.low);
  const gaps: Array<{ gapStart: number; gapEnd: number }> = [];

  // Find the overall overlap region of all channels
  // A gap exists when ANY channel's low is above the max of all previous channels' highs
  let maxHighSoFar = sorted[0].high;

  for (let i = 1; i < sorted.length; i++) {
    if (sorted[i].low > maxHighSoFar) {
      gaps.push({ gapStart: maxHighSoFar, gapEnd: sorted[i].low });
    }
    maxHighSoFar = Math.max(maxHighSoFar, sorted[i].high);
  }

  return gaps;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export const OverlapDetector: React.FC<OverlapDetectorProps> = ({ channels, className }) => {
  const { scaledChannels, gaps, svgHeight } = useMemo(() => {
    if (channels.length === 0) {
      return { scaledChannels: [], gaps: [], svgHeight: 40 };
    }

    const allLows = channels.map((c) => c.low);
    const allHighs = channels.map((c) => c.high);
    const min = Math.min(...allLows);
    const max = Math.max(...allHighs);
    const padding = (max - min) * 0.1 || 0.5;
    const gMin = min - padding;
    const gRange = max - min + padding * 2;

    const toX = (val: number) => CHART_LEFT + ((val - gMin) / gRange) * CHART_WIDTH;

    const scaled = channels.map((ch) => ({
      ...ch,
      x1: toX(ch.low),
      x2: toX(ch.high),
      xPoint: toX(ch.point),
    }));

    const rawGaps = findGaps(channels);
    const scaledGaps = rawGaps.map((g) => ({
      x1: toX(g.gapStart),
      x2: toX(g.gapEnd),
    }));

    const height = channels.length * SVG_HEIGHT_PER_BAR + 24; // 24 for top/bottom padding

    return {
      scaledChannels: scaled,
      gaps: scaledGaps,
      svgHeight: height,
    };
  }, [channels]);

  if (channels.length === 0) return null;

  // Build the aria label
  const hasGaps = gaps.length > 0;
  const ariaLabel = hasGaps
    ? `Confidence interval overlap detector: ${channels.length} channels shown. Clear separation detected — winner identifiable.`
    : `Confidence interval overlap detector: ${channels.length} channels shown. Ranges overlap — no clear winner.`;

  return (
    <div
      className={cn(
        'rounded-lg border border-border bg-card p-4',
        className,
      )}
    >
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-semibold text-foreground tracking-tight uppercase">
          Overlap Detector
        </h3>
        <span
          className={cn(
            'px-2 py-0.5 rounded text-[10px] font-mono border',
            hasGaps
              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
              : 'bg-amber-500/10 text-amber-400 border-amber-500/20',
          )}
        >
          {hasGaps ? 'Clear Winner' : 'Ranges Overlap'}
        </span>
      </div>

      <svg
        width="100%"
        viewBox={`0 0 ${SVG_WIDTH} ${svgHeight}`}
        aria-label={ariaLabel}
        role="img"
        className="overflow-visible"
      >
        <defs>
          {/* Pulse animation for gap highlights — respects prefers-reduced-motion */}
          <style>{`
            @keyframes atlas-gap-pulse {
              0%, 100% { opacity: 0.3; }
              50% { opacity: 0.8; }
            }
            .atlas-gap-highlight {
              animation: atlas-gap-pulse 3s ease-in-out infinite;
            }
            @media (prefers-reduced-motion: reduce) {
              .atlas-gap-highlight {
                animation: none;
                opacity: 0.5;
              }
            }
          `}</style>
        </defs>

        {/* Gap highlights — rendered behind bars */}
        {gaps.map((gap, i) => (
          <rect
            key={`gap-${i}`}
            x={gap.x1}
            y={4}
            width={gap.x2 - gap.x1}
            height={svgHeight - 8}
            rx={3}
            fill="url(#atlas-gap-gradient)"
            className="atlas-gap-highlight"
          />
        ))}

        {/* Gap gradient */}
        {gaps.length > 0 && (
          <defs>
            <linearGradient id="atlas-gap-gradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#10b981" stopOpacity="0.15" />
              <stop offset="50%" stopColor="#10b981" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#10b981" stopOpacity="0.15" />
            </linearGradient>
          </defs>
        )}

        {/* Channel bars */}
        {scaledChannels.map((ch, i) => {
          const y = 12 + i * SVG_HEIGHT_PER_BAR;
          const barY = y + (SVG_HEIGHT_PER_BAR - BAR_HEIGHT) / 2;

          return (
            <g key={ch.name}>
              {/* Channel label */}
              <text
                x={LABEL_WIDTH}
                y={y + SVG_HEIGHT_PER_BAR / 2}
                textAnchor="end"
                dominantBaseline="central"
                className="fill-muted-foreground"
                fontSize="11"
                fontFamily="ui-monospace, monospace"
              >
                {ch.name}
              </text>

              {/* Range bar (low-to-high) */}
              <rect
                x={ch.x1}
                y={barY}
                width={Math.max(ch.x2 - ch.x1, 2)}
                height={BAR_HEIGHT}
                rx={3}
                fill={ch.color}
                opacity={0.3}
              />

              {/* Inner range bar — narrower, more opaque */}
              <rect
                x={ch.x1 + 1}
                y={barY + 2}
                width={Math.max(ch.x2 - ch.x1 - 2, 1)}
                height={BAR_HEIGHT - 4}
                rx={2}
                fill={ch.color}
                opacity={0.6}
              />

              {/* Point estimate marker */}
              <circle
                cx={ch.xPoint}
                cy={y + SVG_HEIGHT_PER_BAR / 2}
                r={POINT_RADIUS}
                fill={ch.color}
                stroke="var(--card)"
                strokeWidth={2}
              />

              {/* Low label */}
              <text
                x={ch.x1}
                y={barY + BAR_HEIGHT + 10}
                textAnchor="middle"
                className="fill-muted-foreground/60"
                fontSize="8"
                fontFamily="ui-monospace, monospace"
              >
                {ch.low.toFixed(2)}
              </text>

              {/* High label */}
              <text
                x={ch.x2}
                y={barY + BAR_HEIGHT + 10}
                textAnchor="middle"
                className="fill-muted-foreground/60"
                fontSize="8"
                fontFamily="ui-monospace, monospace"
              >
                {ch.high.toFixed(2)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
};
