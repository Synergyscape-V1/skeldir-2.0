/**
 * DA-2 DOSSIER -- Historical Performance Trend Section
 *
 * Section 05: Recharts LineChart with ROAS over time, confidence band
 * rendered as a transparent area, dark-theme compatible styling.
 * Every axis and data point carries evidence context.
 */
import React, { useEffect } from 'react';
import {
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer,
  ComposedChart,
} from 'recharts';
import type { ChannelDetailData, ConfidenceLevel } from '../../shared/types';

/* ── Google Fonts ─────────────────────────────────────────── */
const FONT_LINK_ID = 'da2-google-fonts';
function ensureFonts() {
  if (typeof document === 'undefined') return;
  if (document.getElementById(FONT_LINK_ID)) return;
  const link = document.createElement('link');
  link.id = FONT_LINK_ID;
  link.rel = 'stylesheet';
  link.href =
    'https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&family=Syne:wght@500;600;700&display=swap';
  document.head.appendChild(link);
}

/* ── Design Tokens ────────────────────────────────────────── */
const COLORS = {
  pageBg: '#0A0E1A',
  cardBg: '#111827',
  nestedBg: '#1F2937',
  text: {
    primary: '#F0F4FF',
    secondary: '#8B9AB8',
    muted: '#4A5568',
  },
  brand: '#3D7BF5',
  confidence: {
    high: '#10D98C',
    medium: '#F5A623',
    low: '#F04E4E',
  } as Record<ConfidenceLevel, string>,
  border: {
    subtle: 'rgba(139,154,184,0.12)',
    default: 'rgba(139,154,184,0.24)',
  },
} as const;

const FONT = {
  heading: "'Syne', sans-serif",
  body: "'IBM Plex Sans', sans-serif",
  mono: "'IBM Plex Mono', monospace",
} as const;

/* ── Styles ───────────────────────────────────────────────── */
const styles = {
  wrapper: {
    padding: '32px 0 24px',
  } as React.CSSProperties,
  sectionLabel: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    marginBottom: 24,
  } as React.CSSProperties,
  sectionNumber: {
    fontFamily: FONT.mono,
    fontSize: 11,
    fontWeight: 600,
    color: COLORS.text.muted,
    letterSpacing: 2,
    textTransform: 'uppercase' as const,
    minWidth: 32,
  } as React.CSSProperties,
  sectionTitle: {
    fontFamily: FONT.heading,
    fontSize: 11,
    fontWeight: 600,
    color: COLORS.text.muted,
    letterSpacing: 3,
    textTransform: 'uppercase' as const,
  } as React.CSSProperties,
  dividerLine: {
    flex: 1,
    height: 1,
    background: COLORS.border.subtle,
  } as React.CSSProperties,
  chartContainer: {
    background: COLORS.nestedBg,
    border: `1px solid ${COLORS.border.subtle}`,
    borderRadius: 6,
    padding: '24px 16px 16px',
  } as React.CSSProperties,
  legend: {
    display: 'flex',
    alignItems: 'center',
    gap: 20,
    padding: '12px 16px 0',
    flexWrap: 'wrap' as const,
  } as React.CSSProperties,
  legendItem: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    fontFamily: FONT.body,
    fontSize: 11,
    fontWeight: 500,
    color: COLORS.text.muted,
    letterSpacing: 0.3,
  } as React.CSSProperties,
  legendLine: (color: string) => ({
    width: 16,
    height: 2,
    background: color,
    borderRadius: 1,
    flexShrink: 0,
  } as React.CSSProperties),
  legendBand: (color: string) => ({
    width: 16,
    height: 10,
    background: `${color}26`,
    borderRadius: 2,
    border: `1px solid ${color}44`,
    flexShrink: 0,
  } as React.CSSProperties),
  citation: {
    fontFamily: FONT.body,
    fontSize: 11,
    fontWeight: 400,
    color: COLORS.text.muted,
    fontStyle: 'italic' as const,
    margin: '12px 0 0',
    lineHeight: 1.5,
    padding: '0 16px',
  } as React.CSSProperties,
} as const;

/* ── Custom Tooltip ──────────────────────────────────────── */
const tooltipStyle: React.CSSProperties = {
  background: COLORS.cardBg,
  border: `1px solid ${COLORS.border.default}`,
  borderRadius: 6,
  padding: '12px 16px',
  boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
};

interface TooltipPayloadItem {
  name?: string;
  value?: number;
  dataKey?: string;
  payload?: Record<string, unknown>;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadItem[];
  label?: string;
  channelColor: string;
}

const CustomTooltip: React.FC<CustomTooltipProps> = ({ active, payload, channelColor }) => {
  if (!active || !payload || payload.length === 0) return null;

  const data = payload[0]?.payload as ChannelDetailData['trendData'][number] | undefined;
  if (!data) return null;

  return (
    <div style={tooltipStyle}>
      <p style={{ fontFamily: FONT.body, fontSize: 12, fontWeight: 600, color: COLORS.text.primary, margin: '0 0 8px' }}>
        {data.dateFormatted}
      </p>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <span style={{ width: 8, height: 8, borderRadius: '50%', background: channelColor, flexShrink: 0 }} />
        <span style={{ fontFamily: FONT.body, fontSize: 12, color: COLORS.text.secondary }}>
          ROAS:
        </span>
        <span style={{ fontFamily: FONT.mono, fontSize: 13, fontWeight: 600, color: COLORS.text.primary }}>
          {data.roasFormatted}
        </span>
      </div>
      <p style={{ fontFamily: FONT.mono, fontSize: 11, color: COLORS.text.muted, margin: '4px 0 0' }}>
        Range: {data.roasRangeLowFormatted} &ndash; {data.roasRangeHighFormatted}
      </p>
      <p style={{ fontFamily: FONT.mono, fontSize: 11, color: COLORS.text.muted, margin: '2px 0 0' }}>
        Revenue: {data.revenueFormatted} | Spend: {data.spendFormatted}
      </p>
    </div>
  );
};

/* ── Component ────────────────────────────────────────────── */
interface TrendSectionProps {
  trendData: ChannelDetailData['trendData'];
  channelColor?: string;
  confidenceLevel?: ConfidenceLevel;
}

export const TrendSection: React.FC<TrendSectionProps> = ({
  trendData,
  channelColor = COLORS.brand,
  confidenceLevel = 'high',
}) => {
  useEffect(() => {
    ensureFonts();
  }, []);

  const bandColor = COLORS.confidence[confidenceLevel];
  const dataPoints = trendData.length;

  return (
    <section style={styles.wrapper} aria-labelledby="da2-section-trend">
      {/* Section label bar */}
      <div style={styles.sectionLabel}>
        <span style={styles.sectionNumber}>05</span>
        <span id="da2-section-trend" style={styles.sectionTitle}>
          Historical Performance
        </span>
        <div style={styles.dividerLine} aria-hidden="true" />
      </div>

      {/* Chart */}
      <div style={styles.chartContainer}>
        <ResponsiveContainer width="100%" height={280}>
          <ComposedChart data={trendData} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
            <CartesianGrid
              stroke={COLORS.border.subtle}
              strokeDasharray="3 3"
              vertical={false}
            />
            <XAxis
              dataKey="dateFormatted"
              tick={{
                fontFamily: FONT.mono,
                fontSize: 11,
                fill: COLORS.text.muted,
              }}
              tickLine={false}
              axisLine={{ stroke: COLORS.border.subtle }}
              interval={Math.max(0, Math.floor(dataPoints / 6) - 1)}
            />
            <YAxis
              tick={{
                fontFamily: FONT.mono,
                fontSize: 11,
                fill: COLORS.text.muted,
              }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(value: number) => `${value}x`}
              width={48}
              domain={['auto', 'auto']}
            />
            <Tooltip
              content={<CustomTooltip channelColor={channelColor} />}
              cursor={{ stroke: COLORS.border.default, strokeDasharray: '4 4' }}
            />

            {/* Confidence band: area between low and high */}
            <Area
              type="monotone"
              dataKey="roasRangeHigh"
              stroke="none"
              fill={bandColor}
              fillOpacity={0.15}
              isAnimationActive={false}
            />
            <Area
              type="monotone"
              dataKey="roasRangeLow"
              stroke="none"
              fill={COLORS.nestedBg}
              fillOpacity={1}
              isAnimationActive={false}
            />

            {/* Main ROAS line */}
            <Line
              type="monotone"
              dataKey="roas"
              stroke={channelColor}
              strokeWidth={2}
              dot={false}
              activeDot={{
                r: 5,
                fill: channelColor,
                stroke: COLORS.cardBg,
                strokeWidth: 2,
              }}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>

        {/* Legend */}
        <div style={styles.legend}>
          <span style={styles.legendItem}>
            <span style={styles.legendLine(channelColor)} />
            ROAS
          </span>
          <span style={styles.legendItem}>
            <span style={styles.legendBand(bandColor)} />
            Confidence Band (90% interval)
          </span>
        </div>
      </div>

      {/* Evidence citation */}
      <p style={styles.citation}>
        Source: {dataPoints} daily data points from verified revenue and platform-reported spend
      </p>
    </section>
  );
};

export default TrendSection;
