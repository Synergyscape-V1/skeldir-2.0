/**
 * DA-4 ANALYST — Trend Section
 *
 * Compact ROAS trend chart for the left panel of the split-pane layout.
 * Uses Recharts AreaChart with dark-themed axes and grid.
 * ROAS line in channel color, confidence band at 15% opacity.
 * Height ~220px for compact fit in the analyst workstation.
 */

import React from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer,
} from 'recharts';
import type { ChannelDetailData, ConfidenceLevel } from '../../shared/types';
import { CHANNEL_COLORS } from '../../shared/types';

/* ── Design Tokens ──────────────────────────────────────────────── */
const tokens = {
  bg: {
    card: '#111827',
    nested: '#1F2937',
    elevated: '#263244',
  },
  text: {
    primary: '#F0F4FF',
    secondary: '#8B9AB8',
    muted: '#4A5568',
  },
  confidence: {
    high: '#10D98C',
    medium: '#F5A623',
    low: '#F04E4E',
  },
  border: {
    subtle: 'rgba(139,154,184,0.12)',
  },
  font: {
    heading: "'Syne', sans-serif",
    body: "'IBM Plex Sans', sans-serif",
    mono: "'IBM Plex Mono', monospace",
  },
} as const;

/* ── Custom Tooltip ─────────────────────────────────────────────── */
interface TooltipPayloadEntry {
  dataKey: string;
  value: number;
  payload: ChannelDetailData['trendData'][number];
}

const CustomTooltip: React.FC<{
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  label?: string;
}> = ({ active, payload }) => {
  if (!active || !payload || payload.length === 0) return null;

  const entry = payload[0]?.payload;
  if (!entry) return null;

  return (
    <div
      style={{
        backgroundColor: tokens.bg.elevated,
        border: `1px solid ${tokens.border.subtle}`,
        borderRadius: '6px',
        padding: '10px 14px',
        minWidth: '140px',
      }}
    >
      <div
        style={{
          fontFamily: tokens.font.mono,
          fontSize: '11px',
          fontWeight: 400,
          color: tokens.text.muted,
          marginBottom: '6px',
        }}
      >
        {entry.dateFormatted}
      </div>
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '4px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '16px' }}>
          <span
            style={{
              fontFamily: tokens.font.body,
              fontSize: '12px',
              color: tokens.text.secondary,
            }}
          >
            ROAS
          </span>
          <span
            style={{
              fontFamily: tokens.font.mono,
              fontSize: '12px',
              fontWeight: 600,
              color: tokens.text.primary,
            }}
          >
            {entry.roasFormatted}
          </span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '16px' }}>
          <span
            style={{
              fontFamily: tokens.font.body,
              fontSize: '12px',
              color: tokens.text.secondary,
            }}
          >
            Range
          </span>
          <span
            style={{
              fontFamily: tokens.font.mono,
              fontSize: '12px',
              fontWeight: 400,
              color: tokens.text.muted,
            }}
          >
            {entry.roasRangeLowFormatted} – {entry.roasRangeHighFormatted}
          </span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '16px' }}>
          <span
            style={{
              fontFamily: tokens.font.body,
              fontSize: '12px',
              color: tokens.text.secondary,
            }}
          >
            Revenue
          </span>
          <span
            style={{
              fontFamily: tokens.font.mono,
              fontSize: '12px',
              fontWeight: 500,
              color: tokens.text.primary,
            }}
          >
            {entry.revenueFormatted}
          </span>
        </div>
      </div>
    </div>
  );
};

/* ── Props ──────────────────────────────────────────────────────── */
interface TrendSectionProps {
  trendData: ChannelDetailData['trendData'];
  channelColor?: string;
  confidenceLevel?: ConfidenceLevel;
}

/* ── Component ──────────────────────────────────────────────────── */
export const TrendSection: React.FC<TrendSectionProps> = ({
  trendData,
  channelColor,
  confidenceLevel = 'high',
}) => {
  const lineColor = channelColor || CHANNEL_COLORS['facebook'];
  const bandColor = tokens.confidence[confidenceLevel];

  return (
    <>
      <style>
        {'@import url("https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700&family=IBM+Plex+Sans:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600;700&display=swap");'}
      </style>
      <div
        style={{
          backgroundColor: tokens.bg.card,
          border: `1px solid ${tokens.border.subtle}`,
          borderRadius: '8px',
          padding: '20px',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px',
        }}
        role="region"
        aria-label="ROAS trend chart"
      >
        {/* Section heading */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <h3
            style={{
              fontFamily: tokens.font.heading,
              fontSize: '14px',
              fontWeight: 600,
              color: tokens.text.primary,
              margin: 0,
            }}
          >
            ROAS Trend
          </h3>
          <span
            style={{
              fontFamily: tokens.font.mono,
              fontSize: '11px',
              color: tokens.text.muted,
            }}
          >
            30 days
          </span>
        </div>

        {/* Chart */}
        <div style={{ width: '100%', height: '220px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart
              data={trendData}
              margin={{ top: 8, right: 8, left: -8, bottom: 4 }}
            >
              <defs>
                <linearGradient id="da4-roas-gradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={lineColor} stopOpacity={0.25} />
                  <stop offset="95%" stopColor={lineColor} stopOpacity={0.02} />
                </linearGradient>
                <linearGradient id="da4-band-gradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={bandColor} stopOpacity={0.15} />
                  <stop offset="100%" stopColor={bandColor} stopOpacity={0.03} />
                </linearGradient>
              </defs>

              <CartesianGrid
                strokeDasharray="3 3"
                stroke={tokens.border.subtle}
                vertical={false}
              />

              <XAxis
                dataKey="dateFormatted"
                tick={{
                  fontFamily: tokens.font.mono,
                  fontSize: 10,
                  fill: tokens.text.muted,
                }}
                axisLine={{ stroke: tokens.border.subtle }}
                tickLine={false}
                interval="preserveStartEnd"
              />

              <YAxis
                tick={{
                  fontFamily: tokens.font.mono,
                  fontSize: 10,
                  fill: tokens.text.muted,
                }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v: number) => `${v}x`}
                domain={['auto', 'auto']}
                width={42}
              />

              <Tooltip
                content={<CustomTooltip />}
                cursor={{ stroke: tokens.text.muted, strokeDasharray: '3 3' }}
              />

              {/* Confidence band area (high range) */}
              <Area
                type="monotone"
                dataKey="roasRangeHigh"
                stroke="none"
                fill="url(#da4-band-gradient)"
                fillOpacity={1}
                isAnimationActive={false}
              />

              {/* Confidence band area (low range) — subtractive baseline */}
              <Area
                type="monotone"
                dataKey="roasRangeLow"
                stroke="none"
                fill={tokens.bg.card}
                fillOpacity={1}
                isAnimationActive={false}
              />

              {/* ROAS main line */}
              <Area
                type="monotone"
                dataKey="roas"
                stroke={lineColor}
                strokeWidth={2}
                fill="url(#da4-roas-gradient)"
                fillOpacity={1}
                dot={false}
                activeDot={{
                  r: 4,
                  fill: lineColor,
                  stroke: tokens.bg.card,
                  strokeWidth: 2,
                }}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </>
  );
};

export default TrendSection;
