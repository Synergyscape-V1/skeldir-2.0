/**
 * TrendSparkline — Inline mini line chart for A1-SENTINEL
 *
 * Renders a 5-point trend line inside a table cell.
 * Color encodes trend direction (up=green, stable=blue, down=red).
 * Includes a faint confidence band behind the line.
 */

import React from 'react';
import type { TrendDirection } from '@/pages/channel-comparison/shared/types';

interface TrendSparklineProps {
  data: Array<{ roas: number; roasLow: number; roasHigh: number }>;
  trend: TrendDirection;
  width?: number;
  height?: number;
}

const TREND_COLORS: Record<TrendDirection, string> = {
  up: 'rgb(16, 185, 129)',
  stable: 'rgb(96, 165, 250)',
  down: 'rgb(239, 68, 68)',
};

export const TrendSparkline: React.FC<TrendSparklineProps> = ({
  data,
  trend,
  width = 80,
  height = 24,
}) => {
  if (data.length === 0) return null;

  const allValues = data.flatMap((d) => [d.roasLow, d.roasHigh]);
  const min = Math.min(...allValues);
  const max = Math.max(...allValues);
  const range = max - min || 1;

  const padX = 3;
  const padY = 3;
  const plotW = width - padX * 2;
  const plotH = height - padY * 2;

  const toX = (i: number) => padX + (i / (data.length - 1)) * plotW;
  const toY = (v: number) => padY + plotH - ((v - min) / range) * plotH;

  const linePath = data.map((d, i) => `${i === 0 ? 'M' : 'L'}${toX(i)},${toY(d.roas)}`).join(' ');

  // Confidence band (upper boundary forward, lower boundary backward)
  const bandPath =
    data.map((d, i) => `${i === 0 ? 'M' : 'L'}${toX(i)},${toY(d.roasHigh)}`).join(' ') +
    ' ' +
    [...data].reverse().map((d, i) => `L${toX(data.length - 1 - i)},${toY(d.roasLow)}`).join(' ') +
    ' Z';

  const color = TREND_COLORS[trend];

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      xmlns="http://www.w3.org/2000/svg"
      aria-label={`Trend: ${trend}`}
      role="img"
      style={{ display: 'block' }}
    >
      {/* Confidence band */}
      <path d={bandPath} fill={color} opacity={0.08} />
      {/* Trend line */}
      <path d={linePath} fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
      {/* End dot */}
      <circle cx={toX(data.length - 1)} cy={toY(data[data.length - 1].roas)} r={2} fill={color} />
    </svg>
  );
};
