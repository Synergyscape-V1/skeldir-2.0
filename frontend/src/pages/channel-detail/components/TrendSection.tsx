/**
 * Final Single Channel Detail — ROAS Trend Line Graph
 *
 * Based on DA-3 TIMELINE's hero trend component.
 * Adapted for light theme: white card surface, dark text, light grid.
 *
 * Features:
 * - AreaChart with ROAS line in channel color
 * - Confidence river (area between roasRangeLow/High) at 12% opacity
 * - Custom tooltip with full breakdowns
 * - All values pre-formatted from API
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
import type { ChannelDetailData, ConfidenceLevel } from '@/explorations/channel-detail/shared/types';
import { tokens, CHANNEL_COLORS } from '../tokens';

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
  const dp = payload[0]?.payload;
  if (!dp) return null;

  return (
    <div
      style={{
        background: tokens.bg.card,
        border: `1px solid ${tokens.border.default}`,
        borderRadius: tokens.radius.md,
        padding: '12px 16px',
        minWidth: '160px',
        boxShadow: tokens.shadow.lg,
      }}
    >
      <div style={{ fontFamily: tokens.font.body, fontSize: '11px', color: tokens.text.muted, marginBottom: '8px' }}>
        {dp.dateFormatted}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '16px' }}>
          <span style={{ fontFamily: tokens.font.body, fontSize: '12px', color: tokens.text.secondary }}>ROAS</span>
          <span style={{ fontFamily: tokens.font.mono, fontSize: '14px', fontWeight: 600, color: channelColor }}>{dp.roasFormatted}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '16px' }}>
          <span style={{ fontFamily: tokens.font.body, fontSize: '12px', color: tokens.text.secondary }}>Range</span>
          <span style={{ fontFamily: tokens.font.mono, fontSize: '12px', color: tokens.text.muted }}>{dp.roasRangeLowFormatted} – {dp.roasRangeHighFormatted}</span>
        </div>
        <div style={{ borderTop: `1px solid ${tokens.border.subtle}`, paddingTop: '6px', marginTop: '2px', display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '16px' }}>
          <span style={{ fontFamily: tokens.font.body, fontSize: '12px', color: tokens.text.secondary }}>Revenue</span>
          <span style={{ fontFamily: tokens.font.mono, fontSize: '12px', color: tokens.text.primary }}>{dp.revenueFormatted}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '16px' }}>
          <span style={{ fontFamily: tokens.font.body, fontSize: '12px', color: tokens.text.secondary }}>Spend</span>
          <span style={{ fontFamily: tokens.font.mono, fontSize: '12px', color: tokens.text.primary }}>{dp.spendFormatted}</span>
        </div>
      </div>
    </div>
  );
};

/* -- Active Dot ----------------------------------------------------------- */
const ActiveDot: React.FC<{ cx?: number; cy?: number; channelColor: string }> = ({ cx, cy, channelColor }) => {
  if (cx == null || cy == null) return null;
  return (
    <g>
      <circle cx={cx} cy={cy} r={8} fill={channelColor} opacity={0.15} />
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
  channelColor = CHANNEL_COLORS['meta'],
  confidenceLevel = 'high',
}) => {
  const confidenceColor = tokens.confidence[confidenceLevel];

  return (
    <section
      role="region"
      aria-label="ROAS timeline with confidence band"
      style={{
        background: tokens.bg.card,
        borderRadius: tokens.radius.md,
        border: `1px solid ${tokens.border.default}`,
        padding: '24px 24px 16px',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
        boxShadow: tokens.shadow.sm,
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h3 style={{ fontFamily: tokens.font.heading, fontSize: '16px', fontWeight: 600, color: tokens.text.primary, margin: 0 }}>
          ROAS Timeline
        </h3>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <div aria-hidden="true" style={{ width: '16px', height: '2px', borderRadius: '1px', backgroundColor: channelColor }} />
            <span style={{ fontFamily: tokens.font.body, fontSize: '11px', color: tokens.text.muted }}>ROAS</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <div aria-hidden="true" style={{ width: '16px', height: '6px', borderRadius: '3px', backgroundColor: `${confidenceColor}25`, border: `1px solid ${confidenceColor}40` }} />
            <span style={{ fontFamily: tokens.font.body, fontSize: '11px', color: tokens.text.muted }}>Confidence Band</span>
          </div>
        </div>
      </div>

      {/* Chart */}
      <div style={{ width: '100%', height: '320px' }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={trendData} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
            <defs>
              <linearGradient id="final-confidence-river" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={confidenceColor} stopOpacity={0.12} />
                <stop offset="50%" stopColor={confidenceColor} stopOpacity={0.08} />
                <stop offset="100%" stopColor={confidenceColor} stopOpacity={0.02} />
              </linearGradient>
              <linearGradient id="final-roas-fill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={channelColor} stopOpacity={0.10} />
                <stop offset="100%" stopColor={channelColor} stopOpacity={0.01} />
              </linearGradient>
            </defs>

            <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.05)" vertical={false} />

            <XAxis
              dataKey="dateFormatted"
              axisLine={{ stroke: 'rgba(0,0,0,0.08)' }}
              tickLine={false}
              tick={{ fontFamily: tokens.font.mono, fontSize: 10, fill: tokens.text.muted }}
              interval="preserveStartEnd"
              tickMargin={8}
            />

            <YAxis
              axisLine={false}
              tickLine={false}
              tick={{ fontFamily: tokens.font.mono, fontSize: 10, fill: tokens.text.muted }}
              tickFormatter={(v: number) => `${v}x`}
              width={42}
              domain={['auto', 'auto']}
            />

            <Tooltip
              content={<CustomTooltip channelColor={channelColor} />}
              cursor={{ stroke: 'rgba(0,0,0,0.1)', strokeWidth: 1, strokeDasharray: '4 4' }}
            />

            {/* Confidence river */}
            <Area type="monotone" dataKey="roasRangeHigh" stroke="none" fill="url(#final-confidence-river)" fillOpacity={1} isAnimationActive={false} />
            <Area type="monotone" dataKey="roasRangeLow" stroke="none" fill={tokens.bg.card} fillOpacity={1} isAnimationActive={false} />

            {/* Main ROAS line */}
            <Area
              type="monotone"
              dataKey="roas"
              stroke={channelColor}
              strokeWidth={2}
              fill="url(#final-roas-fill)"
              fillOpacity={1}
              dot={false}
              activeDot={<ActiveDot channelColor={channelColor} />}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
};

export default TrendSection;
