/**
 * DA-3 TIMELINE — Trend Section (HERO ELEMENT)
 *
 * Full-width timeline ribbon with confidence river.
 * Uses Recharts AreaChart for the ROAS trend over time.
 *
 * Main line: ROAS in channel color
 * Confidence river: Area between roasRangeLow and roasRangeHigh
 *   filled with confidence-level color at 12% opacity.
 *   Narrow band = high confidence. Wide band = low confidence.
 *
 * Dark theme grid lines, clean date labels, custom tooltip.
 * All values arrive pre-formatted. No client-side calculations.
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

/* -- Design Tokens -------------------------------------------------------- */
const tokens = {
  bg: {
    card: '#111827',
    nested: '#1F2937',
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
  channelDefault: '#3D7BF5',
  border: {
    subtle: 'rgba(139,154,184,0.12)',
  },
  font: {
    heading: "'Syne', sans-serif",
    body: "'IBM Plex Sans', sans-serif",
    mono: "'IBM Plex Mono', monospace",
  },
} as const;

/* -- Custom Tooltip ------------------------------------------------------- */
interface TooltipPayloadItem {
  value: number;
  dataKey: string;
  payload: ChannelDetailData['trendData'][0];
}

const CustomTooltip: React.FC<{
  active?: boolean;
  payload?: TooltipPayloadItem[];
  channelColor: string;
}> = ({ active, payload, channelColor }) => {
  if (!active || !payload || payload.length === 0) return null;

  const dataPoint = payload[0]?.payload;
  if (!dataPoint) return null;

  return (
    <div
      style={{
        background: 'rgba(17,24,39,0.95)',
        backdropFilter: 'blur(8px)',
        border: `1px solid rgba(139,154,184,0.24)`,
        borderRadius: '8px',
        padding: '12px 16px',
        minWidth: '160px',
      }}
    >
      <div
        style={{
          fontFamily: tokens.font.body,
          fontSize: '11px',
          color: tokens.text.muted,
          marginBottom: '8px',
        }}
      >
        {dataPoint.dateFormatted}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '16px' }}>
          <span style={{ fontFamily: tokens.font.body, fontSize: '12px', color: tokens.text.secondary }}>
            ROAS
          </span>
          <span style={{ fontFamily: tokens.font.mono, fontSize: '14px', fontWeight: 600, color: channelColor }}>
            {dataPoint.roasFormatted}
          </span>
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '16px' }}>
          <span style={{ fontFamily: tokens.font.body, fontSize: '12px', color: tokens.text.secondary }}>
            Range
          </span>
          <span style={{ fontFamily: tokens.font.mono, fontSize: '12px', color: tokens.text.muted }}>
            {dataPoint.roasRangeLowFormatted} – {dataPoint.roasRangeHighFormatted}
          </span>
        </div>

        <div
          style={{
            borderTop: `1px solid ${tokens.border.subtle}`,
            paddingTop: '6px',
            marginTop: '2px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'baseline',
            gap: '16px',
          }}
        >
          <span style={{ fontFamily: tokens.font.body, fontSize: '12px', color: tokens.text.secondary }}>
            Revenue
          </span>
          <span style={{ fontFamily: tokens.font.mono, fontSize: '12px', color: tokens.text.primary }}>
            {dataPoint.revenueFormatted}
          </span>
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '16px' }}>
          <span style={{ fontFamily: tokens.font.body, fontSize: '12px', color: tokens.text.secondary }}>
            Spend
          </span>
          <span style={{ fontFamily: tokens.font.mono, fontSize: '12px', color: tokens.text.primary }}>
            {dataPoint.spendFormatted}
          </span>
        </div>
      </div>
    </div>
  );
};

/* -- Custom Active Dot ---------------------------------------------------- */
const ActiveDot: React.FC<{
  cx?: number;
  cy?: number;
  channelColor: string;
}> = ({ cx, cy, channelColor }) => {
  if (cx == null || cy == null) return null;
  return (
    <g>
      <circle cx={cx} cy={cy} r={8} fill={channelColor} opacity={0.2} />
      <circle cx={cx} cy={cy} r={4} fill={channelColor} stroke={tokens.bg.card} strokeWidth={2} />
    </g>
  );
};

/* -- Component ------------------------------------------------------------ */

interface TrendSectionProps {
  trendData: ChannelDetailData['trendData'];
  channelColor?: string;
  confidenceLevel?: ConfidenceLevel;
}

export const TrendSection: React.FC<TrendSectionProps> = ({
  trendData,
  channelColor = tokens.channelDefault,
  confidenceLevel = 'high',
}) => {
  const confidenceColor = tokens.confidence[confidenceLevel];

  return (
    <section
      role="region"
      aria-label="ROAS timeline with confidence band"
      style={{
        background: tokens.bg.card,
        borderRadius: '8px',
        border: `1px solid ${tokens.border.subtle}`,
        padding: '24px 24px 16px 24px',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h3
          style={{
            fontFamily: tokens.font.heading,
            fontSize: '16px',
            fontWeight: 600,
            color: tokens.text.primary,
            margin: 0,
          }}
        >
          ROAS Timeline
        </h3>

        {/* Legend */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <div
              aria-hidden="true"
              style={{
                width: '16px',
                height: '2px',
                borderRadius: '1px',
                backgroundColor: channelColor,
              }}
            />
            <span style={{ fontFamily: tokens.font.body, fontSize: '11px', color: tokens.text.muted }}>
              ROAS
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <div
              aria-hidden="true"
              style={{
                width: '16px',
                height: '6px',
                borderRadius: '3px',
                backgroundColor: `${confidenceColor}30`,
                border: `1px solid ${confidenceColor}40`,
              }}
            />
            <span style={{ fontFamily: tokens.font.body, fontSize: '11px', color: tokens.text.muted }}>
              Confidence Band
            </span>
          </div>
        </div>
      </div>

      {/* Chart */}
      <div style={{ width: '100%', height: '320px' }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={trendData}
            margin={{ top: 8, right: 8, bottom: 0, left: -8 }}
          >
            <defs>
              {/* Confidence river gradient */}
              <linearGradient id="da3-confidence-river" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={confidenceColor} stopOpacity={0.12} />
                <stop offset="50%" stopColor={confidenceColor} stopOpacity={0.08} />
                <stop offset="100%" stopColor={confidenceColor} stopOpacity={0.02} />
              </linearGradient>

              {/* Main line gradient */}
              <linearGradient id="da3-roas-fill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={channelColor} stopOpacity={0.15} />
                <stop offset="100%" stopColor={channelColor} stopOpacity={0.01} />
              </linearGradient>
            </defs>

            <CartesianGrid
              strokeDasharray="3 3"
              stroke="rgba(255,255,255,0.05)"
              vertical={false}
            />

            <XAxis
              dataKey="dateFormatted"
              axisLine={{ stroke: 'rgba(255,255,255,0.05)' }}
              tickLine={false}
              tick={{
                fontFamily: tokens.font.mono,
                fontSize: 10,
                fill: tokens.text.muted,
              }}
              interval="preserveStartEnd"
              tickMargin={8}
            />

            <YAxis
              axisLine={false}
              tickLine={false}
              tick={{
                fontFamily: tokens.font.mono,
                fontSize: 10,
                fill: tokens.text.muted,
              }}
              tickFormatter={(v: number) => `${v}x`}
              width={42}
              domain={['auto', 'auto']}
            />

            <Tooltip
              content={<CustomTooltip channelColor={channelColor} />}
              cursor={{
                stroke: 'rgba(139,154,184,0.2)',
                strokeWidth: 1,
                strokeDasharray: '4 4',
              }}
            />

            {/* Confidence river — the area between low and high range */}
            <Area
              type="monotone"
              dataKey="roasRangeHigh"
              stroke="none"
              fill="url(#da3-confidence-river)"
              fillOpacity={1}
              isAnimationActive={false}
            />
            <Area
              type="monotone"
              dataKey="roasRangeLow"
              stroke="none"
              fill={tokens.bg.card}
              fillOpacity={1}
              isAnimationActive={false}
            />

            {/* Main ROAS line with subtle fill */}
            <Area
              type="monotone"
              dataKey="roas"
              stroke={channelColor}
              strokeWidth={2}
              fill="url(#da3-roas-fill)"
              fillOpacity={1}
              dot={false}
              activeDot={
                <ActiveDot channelColor={channelColor} />
              }
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
};

export default TrendSection;
