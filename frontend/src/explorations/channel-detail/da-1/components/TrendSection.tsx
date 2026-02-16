/**
 * DA-1 COCKPIT — Trend Section
 *
 * Historical ROAS trend chart using Recharts.
 * AreaChart with ROAS line in channel color and confidence band
 * shaded between roasRangeLow and roasRangeHigh at 15% opacity.
 *
 * Custom dark-themed tooltip. All values pre-formatted from API.
 * No client-side calculations.
 */

import React, { useId } from 'react';
import {
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer,
  Line,
  ComposedChart,
} from 'recharts';
import type { ChannelDetailData, ConfidenceLevel } from '../../shared/types';

/* ── Design Tokens ──────────────────────────────────────────────── */
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
  border: {
    subtle: 'rgba(139,154,184,0.12)',
  },
  font: {
    heading: "'Syne', sans-serif",
    body: "'IBM Plex Sans', sans-serif",
    mono: "'IBM Plex Mono', monospace",
  },
} as const;

function getConfidenceColor(level: ConfidenceLevel): string {
  return tokens.confidence[level];
}

/* ── Custom Tooltip ────────────────────────────────────────────── */

interface TooltipPayloadItem {
  dataKey: string;
  value: number;
  payload: ChannelDetailData['trendData'][number];
}

const CustomTooltip: React.FC<{
  active?: boolean;
  payload?: TooltipPayloadItem[];
  label?: string;
  channelColor: string;
  confidenceColor: string;
}> = ({ active, payload, channelColor, confidenceColor }) => {
  if (!active || !payload || payload.length === 0) return null;

  const data = payload[0]?.payload;
  if (!data) return null;

  return (
    <div
      style={{
        background: tokens.bg.nested,
        border: `1px solid ${tokens.border.subtle}`,
        borderRadius: '8px',
        padding: '12px 16px',
        minWidth: '180px',
        boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
      }}
    >
      <div
        style={{
          fontFamily: tokens.font.body,
          fontSize: '12px',
          fontWeight: 600,
          color: tokens.text.primary,
          marginBottom: '10px',
          paddingBottom: '6px',
          borderBottom: `1px solid ${tokens.border.subtle}`,
        }}
      >
        {data.dateFormatted}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        {/* ROAS */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <div
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: channelColor,
                flexShrink: 0,
              }}
            />
            <span
              style={{
                fontFamily: tokens.font.body,
                fontSize: '11px',
                color: tokens.text.secondary,
              }}
            >
              ROAS
            </span>
          </div>
          <span
            style={{
              fontFamily: tokens.font.mono,
              fontSize: '12px',
              fontWeight: 600,
              color: tokens.text.primary,
            }}
          >
            {data.roasFormatted}
          </span>
        </div>

        {/* Confidence Range */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <div
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '2px',
                backgroundColor: `${confidenceColor}40`,
                flexShrink: 0,
              }}
            />
            <span
              style={{
                fontFamily: tokens.font.body,
                fontSize: '11px',
                color: tokens.text.secondary,
              }}
            >
              Range
            </span>
          </div>
          <span
            style={{
              fontFamily: tokens.font.mono,
              fontSize: '12px',
              fontWeight: 500,
              color: tokens.text.secondary,
            }}
          >
            {data.roasRangeLowFormatted} – {data.roasRangeHighFormatted}
          </span>
        </div>

        {/* Revenue */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '16px' }}>
          <span
            style={{
              fontFamily: tokens.font.body,
              fontSize: '11px',
              color: tokens.text.muted,
              paddingLeft: '14px',
            }}
          >
            Revenue
          </span>
          <span
            style={{
              fontFamily: tokens.font.mono,
              fontSize: '12px',
              color: tokens.text.secondary,
            }}
          >
            {data.revenueFormatted}
          </span>
        </div>

        {/* Spend */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '16px' }}>
          <span
            style={{
              fontFamily: tokens.font.body,
              fontSize: '11px',
              color: tokens.text.muted,
              paddingLeft: '14px',
            }}
          >
            Spend
          </span>
          <span
            style={{
              fontFamily: tokens.font.mono,
              fontSize: '12px',
              color: tokens.text.secondary,
            }}
          >
            {data.spendFormatted}
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
  channelColor = '#3D7BF5',
  confidenceLevel = 'high',
}) => {
  const sectionId = useId();
  const confidenceColor = getConfidenceColor(confidenceLevel);

  return (
    <section
      aria-labelledby={sectionId}
      style={{
        padding: '24px',
        background: tokens.bg.card,
        borderRadius: '8px',
        border: `1px solid ${tokens.border.subtle}`,
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
      }}
    >
      <style>
        {'@import url("https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700&family=IBM+Plex+Sans:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600;700&display=swap");'}
      </style>

      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        <h3
          id={sectionId}
          style={{
            fontFamily: tokens.font.heading,
            fontSize: '20px',
            fontWeight: 600,
            color: tokens.text.primary,
            margin: 0,
          }}
        >
          ROAS Trend
        </h3>

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          {/* Legend: ROAS line */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <div
              style={{
                width: '16px',
                height: '2px',
                backgroundColor: channelColor,
                borderRadius: '1px',
              }}
            />
            <span
              style={{
                fontFamily: tokens.font.body,
                fontSize: '11px',
                color: tokens.text.secondary,
              }}
            >
              ROAS
            </span>
          </div>

          {/* Legend: Confidence band */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <div
              style={{
                width: '16px',
                height: '8px',
                backgroundColor: `${confidenceColor}26`,
                borderRadius: '2px',
                border: `1px solid ${confidenceColor}40`,
              }}
            />
            <span
              style={{
                fontFamily: tokens.font.body,
                fontSize: '11px',
                color: tokens.text.secondary,
              }}
            >
              Confidence Band
            </span>
          </div>
        </div>
      </div>

      {/* Chart */}
      <div style={{ width: '100%', height: '280px' }}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart
            data={trendData}
            margin={{ top: 8, right: 8, left: -8, bottom: 0 }}
          >
            <defs>
              <linearGradient id={`da1-confidence-fill-${sectionId}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={confidenceColor} stopOpacity={0.15} />
                <stop offset="100%" stopColor={confidenceColor} stopOpacity={0.03} />
              </linearGradient>
            </defs>

            <CartesianGrid
              stroke={tokens.border.subtle}
              strokeDasharray="3 3"
              vertical={false}
            />

            <XAxis
              dataKey="dateFormatted"
              tick={{
                fontFamily: tokens.font.mono,
                fontSize: 10,
                fill: tokens.text.muted,
              }}
              tickLine={false}
              axisLine={{ stroke: tokens.border.subtle }}
              interval="preserveStartEnd"
              minTickGap={40}
            />

            <YAxis
              tick={{
                fontFamily: tokens.font.mono,
                fontSize: 10,
                fill: tokens.text.muted,
              }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(val: number) => `${val.toFixed(1)}x`}
              width={48}
              domain={['auto', 'auto']}
            />

            <Tooltip
              content={
                <CustomTooltip
                  channelColor={channelColor}
                  confidenceColor={confidenceColor}
                />
              }
              cursor={{
                stroke: tokens.text.muted,
                strokeWidth: 1,
                strokeDasharray: '4 4',
              }}
            />

            {/* Confidence band (area between low and high) */}
            <Area
              type="monotone"
              dataKey="roasRangeHigh"
              stroke="none"
              fill={`url(#da1-confidence-fill-${sectionId})`}
              fillOpacity={1}
              isAnimationActive={true}
              animationDuration={800}
            />
            <Area
              type="monotone"
              dataKey="roasRangeLow"
              stroke="none"
              fill={tokens.bg.card}
              fillOpacity={1}
              isAnimationActive={true}
              animationDuration={800}
            />

            {/* ROAS line */}
            <Line
              type="monotone"
              dataKey="roas"
              stroke={channelColor}
              strokeWidth={2}
              dot={false}
              activeDot={{
                r: 4,
                fill: channelColor,
                stroke: tokens.text.primary,
                strokeWidth: 2,
              }}
              isAnimationActive={true}
              animationDuration={1000}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Summary footer */}
      <div
        style={{
          display: 'flex',
          gap: '24px',
          padding: '10px 16px',
          background: tokens.bg.nested,
          borderRadius: '6px',
          flexWrap: 'wrap',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span
            style={{
              fontFamily: tokens.font.body,
              fontSize: '12px',
              color: tokens.text.muted,
            }}
          >
            Data points
          </span>
          <span
            style={{
              fontFamily: tokens.font.mono,
              fontSize: '14px',
              fontWeight: 500,
              color: tokens.text.primary,
            }}
          >
            {trendData.length}
          </span>
        </div>
        {trendData.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span
              style={{
                fontFamily: tokens.font.body,
                fontSize: '12px',
                color: tokens.text.muted,
              }}
            >
              Period
            </span>
            <span
              style={{
                fontFamily: tokens.font.mono,
                fontSize: '14px',
                fontWeight: 500,
                color: tokens.text.primary,
              }}
            >
              {trendData[0].dateFormatted} – {trendData[trendData.length - 1].dateFormatted}
            </span>
          </div>
        )}
      </div>
    </section>
  );
};

export default TrendSection;
