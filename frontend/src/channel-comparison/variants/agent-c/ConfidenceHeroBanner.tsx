import React, { useMemo } from "react";
import type { ComparisonChannelData, WinnerDeclaration } from "../../../types/comparison";
import { CHANNEL_COLORS } from "../../core/constants";
import { displayChannelName } from "../../core/constants";
import { formatROAS } from "../../../lib/formatters";

interface ConfidenceHeroBannerProps {
  channels: ComparisonChannelData[];
  winner: WinnerDeclaration | null;
}

function toX(value: number, min: number, max: number, width: number): number {
  if (max <= min) return 0;
  return ((value - min) / (max - min)) * width;
}

const TIER_COLORS: Record<string, string> = {
  high: "#10b981",
  medium: "#f59e0b",
  low: "#ef4444",
};

export function ConfidenceHeroBanner({ channels, winner }: ConfidenceHeroBannerProps) {
  const CHART_WIDTH = 700;
  const BAND_HEIGHT = 28;
  const BAND_GAP = 12;
  const LABEL_WIDTH = 150;
  const TOP_PADDING = 30;
  const BOTTOM_PADDING = 30;
  const chartAreaWidth = CHART_WIDTH - LABEL_WIDTH;
  const totalHeight = TOP_PADDING + channels.length * (BAND_HEIGHT + BAND_GAP) + BOTTOM_PADDING;

  const min = useMemo(() => Math.min(...channels.map((c) => c.confidenceRange.low)) - 0.3, [channels]);
  const max = useMemo(() => Math.max(...channels.map((c) => c.confidenceRange.high)) + 0.3, [channels]);

  const overlapZone = useMemo(() => {
    if (channels.length < 2) return null;
    const sorted = [...channels].sort((a, b) => b.performance.roas - a.performance.roas);
    const overlapLow = sorted[0].confidenceRange.low;
    const overlapHigh = sorted[1].confidenceRange.high;
    if (overlapLow > overlapHigh) return null;
    return { low: overlapLow, high: overlapHigh };
  }, [channels]);

  const axisTicks = useMemo(() => {
    const steps = 6;
    return Array.from({ length: steps + 1 }, (_, i) => Number((min + ((max - min) / steps) * i).toFixed(2)));
  }, [min, max]);

  return (
    <section className="cc-c-hero-banner" role="figure" aria-label="Confidence range comparison">
      <div className="cc-c-hero-header">
        <h3>Confidence Range Analysis</h3>
        <p className="cc-c-hero-subtitle">
          {winner
            ? `${winner.channelName} leads with non-overlapping confidence — ${formatROAS(winner.roas)} ROAS`
            : "Confidence ranges overlap — no statistically reliable winner yet."}
        </p>
      </div>

      <div className="cc-c-hero-svg-wrap">
        <svg
          viewBox={`0 0 ${CHART_WIDTH} ${totalHeight}`}
          width="100%"
          height={totalHeight}
          preserveAspectRatio="xMidYMid meet"
          className="cc-c-hero-svg"
        >
          <defs>
            <pattern id="cc-c-hatch" patternUnits="userSpaceOnUse" width="8" height="8">
              <path d="M0,8 L8,0" stroke="#6b7280" strokeWidth="1" />
            </pattern>
            <pattern id="cc-c-dots-medium" patternUnits="userSpaceOnUse" width="6" height="6">
              <line x1="0" y1="6" x2="6" y2="0" stroke="currentColor" strokeWidth="0.8" />
            </pattern>
          </defs>

          {/* Axis ticks */}
          {axisTicks.map((tick) => {
            const x = LABEL_WIDTH + toX(tick, min, max, chartAreaWidth);
            return (
              <g key={tick}>
                <line x1={x} y1={TOP_PADDING - 5} x2={x} y2={totalHeight - BOTTOM_PADDING + 5} stroke="#e5e7eb" strokeWidth={1} strokeDasharray="3,3" />
                <text x={x} y={totalHeight - BOTTOM_PADDING + 20} textAnchor="middle" fontSize="10" fill="#9ca3af">{tick.toFixed(1)}</text>
              </g>
            );
          })}

          {/* Overlap zone */}
          {overlapZone ? (
            <rect
              x={LABEL_WIDTH + toX(overlapZone.low, min, max, chartAreaWidth)}
              y={TOP_PADDING - 5}
              width={toX(overlapZone.high, min, max, chartAreaWidth) - toX(overlapZone.low, min, max, chartAreaWidth)}
              height={channels.length * (BAND_HEIGHT + BAND_GAP)}
              fill="url(#cc-c-hatch)"
              opacity={0.25}
            />
          ) : null}

          {/* Channel bands */}
          {channels.map((channel, index) => {
            const y = TOP_PADDING + index * (BAND_HEIGHT + BAND_GAP);
            const tier = channel.confidenceRange.level;
            const tierColor = TIER_COLORS[tier] ?? TIER_COLORS.medium;
            const x1 = LABEL_WIDTH + toX(channel.confidenceRange.low, min, max, chartAreaWidth);
            const x2 = LABEL_WIDTH + toX(channel.confidenceRange.high, min, max, chartAreaWidth);
            const markerX = LABEL_WIDTH + toX(channel.performance.roas, min, max, chartAreaWidth);
            const name = displayChannelName(channel.channel.name, channel.channel.platform_type);

            return (
              <g key={channel.channel.id}>
                {/* Channel label */}
                <text x={LABEL_WIDTH - 10} y={y + BAND_HEIGHT / 2 + 4} textAnchor="end" fontSize="12" fontWeight="600" fill="#374151">
                  {name}
                </text>

                {/* Confidence band */}
                <rect
                  x={x1}
                  y={y}
                  width={Math.max(6, x2 - x1)}
                  height={BAND_HEIGHT}
                  rx={4}
                  fill={tierColor}
                  opacity={0.25}
                />
                <rect
                  x={x1}
                  y={y}
                  width={Math.max(6, x2 - x1)}
                  height={BAND_HEIGHT}
                  rx={4}
                  fill="none"
                  stroke={tierColor}
                  strokeWidth={1.5}
                  opacity={0.6}
                />

                {/* Point estimate diamond marker */}
                <polygon
                  points={`${markerX},${y + 2} ${markerX + 6},${y + BAND_HEIGHT / 2} ${markerX},${y + BAND_HEIGHT - 2} ${markerX - 6},${y + BAND_HEIGHT / 2}`}
                  fill={CHANNEL_COLORS[index] ?? "#3b82f6"}
                  stroke="white"
                  strokeWidth={1.5}
                />

                {/* ROAS value label */}
                <text
                  x={markerX}
                  y={y - 4}
                  textAnchor="middle"
                  fontSize="11"
                  fontWeight="700"
                  fill={CHANNEL_COLORS[index] ?? "#3b82f6"}
                >
                  {channel.performance.roas.toFixed(2)}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      {/* Mobile fallback: vertical list */}
      <div className="cc-c-hero-mobile-fallback">
        {channels.map((channel) => {
          const tier = channel.confidenceRange.level;
          const name = displayChannelName(channel.channel.name, channel.channel.platform_type);
          return (
            <div key={channel.channel.id} className={`cc-c-mobile-row cc-c-mobile-tier-${tier}`}>
              <span className="cc-c-mobile-name">{name}</span>
              <span className="cc-c-mobile-roas">{channel.performance.roas.toFixed(2)}</span>
              <span className="cc-c-mobile-range">
                {channel.confidenceRange.low.toFixed(2)}–{channel.confidenceRange.high.toFixed(2)}
              </span>
              <span className={`cc-c-mobile-badge cc-c-badge-${tier}`}>
                {tier === "high" ? "High" : tier === "medium" ? "Medium" : "Low"} Confidence
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
