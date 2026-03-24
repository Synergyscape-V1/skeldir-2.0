import React, { useMemo } from "react";
import type { ComparisonChannelData } from "../../../types/comparison";
import { CHANNEL_COLORS } from "../../core/constants";
import { displayChannelName } from "../../core/constants";

interface CompactConfidenceOverlayProps {
  channels: ComparisonChannelData[];
}

function toX(value: number, min: number, max: number, width: number): number {
  if (max <= min) return 0;
  return ((value - min) / (max - min)) * width;
}

export function CompactConfidenceOverlay({ channels }: CompactConfidenceOverlayProps) {
  const CHART_WIDTH = 600;
  const CHART_HEIGHT = 60;
  const BAR_HEIGHT = 14;
  const BAR_GAP = 4;
  const TOP_OFFSET = 10;

  const min = useMemo(() => Math.min(...channels.map((c) => c.confidenceRange.low)) - 0.3, [channels]);
  const max = useMemo(() => Math.max(...channels.map((c) => c.confidenceRange.high)) + 0.3, [channels]);

  const rangesOverlap = useMemo(() => {
    if (channels.length < 2) return false;
    const sorted = [...channels].sort((a, b) => b.performance.roas - a.performance.roas);
    return sorted[0].confidenceRange.low <= sorted[1].confidenceRange.high;
  }, [channels]);

  const overlapZone = useMemo(() => {
    if (channels.length < 2 || !rangesOverlap) return null;
    const sorted = [...channels].sort((a, b) => b.performance.roas - a.performance.roas);
    const overlapLow = sorted[0].confidenceRange.low;
    const overlapHigh = sorted[1].confidenceRange.high;
    if (overlapLow > overlapHigh) return null;
    return { low: overlapLow, high: overlapHigh };
  }, [channels, rangesOverlap]);

  const winnerName = useMemo(() => {
    if (rangesOverlap || channels.length < 2) return null;
    const sorted = [...channels].sort((a, b) => b.performance.roas - a.performance.roas);
    return displayChannelName(sorted[0].channel.name, sorted[0].channel.platform_type);
  }, [channels, rangesOverlap]);

  return (
    <div className="cc-b-conf-overlay" role="figure" aria-label="ROAS confidence range overlay">
      <svg
        viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
        width="100%"
        height={CHART_HEIGHT}
        preserveAspectRatio="xMidYMid meet"
      >
        <defs>
          <pattern id="cc-b-hatch" patternUnits="userSpaceOnUse" width="6" height="6">
            <path d="M0,6 L6,0" stroke="#6b7280" strokeWidth="0.8" />
          </pattern>
        </defs>

        {overlapZone ? (
          <rect
            x={toX(overlapZone.low, min, max, CHART_WIDTH)}
            y={0}
            width={toX(overlapZone.high, min, max, CHART_WIDTH) - toX(overlapZone.low, min, max, CHART_WIDTH)}
            height={CHART_HEIGHT}
            fill="url(#cc-b-hatch)"
            opacity={0.4}
          />
        ) : null}

        {channels.map((channel, index) => {
          const y = TOP_OFFSET + index * (BAR_HEIGHT + BAR_GAP);
          const x1 = toX(channel.confidenceRange.low, min, max, CHART_WIDTH);
          const x2 = toX(channel.confidenceRange.high, min, max, CHART_WIDTH);
          const markerX = toX(channel.performance.roas, min, max, CHART_WIDTH);
          const color = CHANNEL_COLORS[index] ?? CHANNEL_COLORS[0];

          return (
            <g key={channel.channel.id}>
              <rect
                x={x1}
                y={y}
                width={Math.max(4, x2 - x1)}
                height={BAR_HEIGHT}
                rx={2}
                fill={color}
                opacity={0.35}
              />
              <line
                x1={markerX}
                y1={y - 2}
                x2={markerX}
                y2={y + BAR_HEIGHT + 2}
                stroke={color}
                strokeWidth={2}
              />
              <text
                x={markerX}
                y={y - 4}
                textAnchor="middle"
                fontSize="9"
                fill={color}
                fontWeight="600"
              >
                {channel.performance.roas.toFixed(2)}
              </text>
            </g>
          );
        })}
      </svg>
      <p className="cc-b-conf-annotation">
        {rangesOverlap
          ? "Overlap detected \u2014 no reliable winner."
          : `Non-overlapping \u2014 ${winnerName} confirmed.`}
      </p>
    </div>
  );
}
