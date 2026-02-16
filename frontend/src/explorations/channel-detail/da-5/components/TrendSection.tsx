/**
 * DA-5 COMPACT — Trend section (expandable)
 *
 * Collapsed: Small sparkline SVG (200x40) showing trend direction
 * Expanded: Full Recharts AreaChart with ROAS + confidence band
 */

import React from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import type { ChannelDetailData } from '../../shared/types';
import type { ConfidenceLevel } from '../../shared/types';

/* ── Design tokens ─────────────────────────────────────────────── */
const T = {
  textPrimary: '#F0F4FF',
  textSecondary: '#8B9AB8',
  textMuted: '#4A5568',
  brand: '#3D7BF5',
  high: '#10D98C',
  medium: '#F5A623',
  low: '#F04E4E',
  card: '#111827',
  nested: '#1F2937',
  borderSubtle: 'rgba(139,154,184,0.12)',
  fontBody: "'IBM Plex Sans', sans-serif",
  fontData: "'IBM Plex Mono', monospace",
};

const CONFIDENCE_COLORS: Record<string, string> = {
  high: T.high,
  medium: T.medium,
  low: T.low,
};

interface TrendSectionProps {
  trendData: ChannelDetailData['trendData'];
  channelColor?: string;
  confidenceLevel?: ConfidenceLevel;
  expanded?: boolean;
}

/* ── Sparkline (collapsed view) ────────────────────────────────── */
const Sparkline: React.FC<{ data: ChannelDetailData['trendData']; color: string }> = ({
  data,
  color,
}) => {
  if (data.length === 0) return null;

  const values = data.map((d) => d.roas);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  const width = 200;
  const height = 40;
  const padding = 2;

  const points = data.map((d, i) => {
    const x = padding + (i / (data.length - 1)) * (width - padding * 2);
    const y = height - padding - ((d.roas - min) / range) * (height - padding * 2);
    return `${x},${y}`;
  });

  const polyline = points.join(' ');

  /* Fill area: close the path at bottom */
  const areaPath =
    `M ${points[0]} ` +
    points.slice(1).map((p) => `L ${p}`).join(' ') +
    ` L ${width - padding},${height} L ${padding},${height} Z`;

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      style={{ display: 'block', margin: '0 auto' }}
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="da5-spark-grad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.2} />
          <stop offset="100%" stopColor={color} stopOpacity={0} />
        </linearGradient>
      </defs>
      <path d={areaPath} fill="url(#da5-spark-grad)" />
      <polyline
        points={polyline}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
};

/* ── Custom tooltip ────────────────────────────────────────────── */
const CustomTooltip: React.FC<any> = ({ active, payload }) => {
  if (!active || !payload || payload.length === 0) return null;
  const d = payload[0]?.payload;
  if (!d) return null;

  return (
    <div
      style={{
        background: T.nested,
        border: `1px solid ${T.borderSubtle}`,
        borderRadius: 6,
        padding: '8px 12px',
        fontFamily: T.fontData,
        fontSize: 12,
      }}
    >
      <p style={{ color: T.textSecondary, margin: 0, marginBottom: 4, fontFamily: T.fontBody }}>
        {d.dateFormatted}
      </p>
      <p style={{ color: T.textPrimary, margin: 0, fontWeight: 600 }}>
        ROAS {d.roasFormatted}
      </p>
      <p style={{ color: T.textMuted, margin: '2px 0 0', fontSize: 11 }}>
        Range: {d.roasRangeLowFormatted} - {d.roasRangeHighFormatted}
      </p>
    </div>
  );
};

/* ── Main component ────────────────────────────────────────────── */
export const TrendSection: React.FC<TrendSectionProps> = ({
  trendData,
  channelColor = T.brand,
  confidenceLevel = 'high',
  expanded = false,
}) => {
  const confColor = CONFIDENCE_COLORS[confidenceLevel] || T.textSecondary;

  if (!expanded) {
    return (
      <div style={{ padding: '12px 0', textAlign: 'center' }}>
        <Sparkline data={trendData} color={channelColor} />
        <p
          style={{
            fontFamily: T.fontBody,
            fontSize: 11,
            color: T.textMuted,
            margin: '6px 0 0',
          }}
        >
          30-day ROAS trend
        </p>
      </div>
    );
  }

  return (
    <div style={{ padding: '16px 0' }}>
      <div style={{ width: '100%', height: 240 }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={trendData} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
            <defs>
              <linearGradient id="da5-trend-roas" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={channelColor} stopOpacity={0.25} />
                <stop offset="100%" stopColor={channelColor} stopOpacity={0} />
              </linearGradient>
              <linearGradient id="da5-trend-band" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={confColor} stopOpacity={0.1} />
                <stop offset="100%" stopColor={confColor} stopOpacity={0.03} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="dateFormatted"
              tick={{ fill: T.textMuted, fontSize: 10, fontFamily: T.fontBody }}
              axisLine={{ stroke: T.borderSubtle }}
              tickLine={false}
              interval={6}
            />
            <YAxis
              tick={{ fill: T.textMuted, fontSize: 10, fontFamily: T.fontData }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v: number) => `${v}x`}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ stroke: T.borderSubtle }} />
            {/* Confidence band */}
            <Area
              type="monotone"
              dataKey="roasRangeHigh"
              stroke="none"
              fill="url(#da5-trend-band)"
              fillOpacity={1}
              isAnimationActive={false}
            />
            <Area
              type="monotone"
              dataKey="roasRangeLow"
              stroke="none"
              fill={T.card}
              fillOpacity={1}
              isAnimationActive={false}
            />
            {/* ROAS line */}
            <Area
              type="monotone"
              dataKey="roas"
              stroke={channelColor}
              strokeWidth={2}
              fill="url(#da5-trend-roas)"
              fillOpacity={1}
              dot={false}
              activeDot={{
                r: 4,
                fill: channelColor,
                stroke: T.card,
                strokeWidth: 2,
              }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
