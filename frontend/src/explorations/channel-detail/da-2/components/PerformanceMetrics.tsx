/**
 * DA-2 DOSSIER — Performance Metrics
 *
 * Section 02: Four metric blocks (Revenue, Spend, ROAS, Conversions) arranged
 * in a 2x2 grid. Each block carries an evidence citation footnote.
 * All values are pre-formatted — no calculations on the frontend.
 */
import React from 'react';
import type { ChannelDetailData } from '../../shared/types';

/* ── Design Tokens ────────────────────────────────────────── */
const COLORS = {
  cardBg: '#111827',
  nestedBg: '#1F2937',
  text: {
    primary: '#F0F4FF',
    secondary: '#8B9AB8',
    muted: '#4A5568',
  },
  positive: '#10D98C',
  negative: '#F04E4E',
  neutral: '#F5A623',
  border: {
    subtle: 'rgba(139,154,184,0.12)',
  },
} as const;

const FONT = {
  heading: "'Syne', sans-serif",
  body: "'IBM Plex Sans', sans-serif",
  mono: "'IBM Plex Mono', monospace",
} as const;

/* ── Delta color logic ────────────────────────────────────── */
function deltaColor(delta: string): string {
  if (delta.startsWith('+')) return COLORS.positive;
  if (delta.startsWith('-')) {
    // For CPA, a negative delta is good
    if (delta.includes('$')) return COLORS.positive;
    return COLORS.negative;
  }
  return COLORS.neutral;
}

/* ── Styles ───────────────────────────────────────────────── */
const styles = {
  wrapper: {
    padding: '32px 0 24px',
    borderBottom: `1px solid ${COLORS.border.subtle}`,
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
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(2, 1fr)',
    gap: 16,
  } as React.CSSProperties,
  card: {
    background: COLORS.nestedBg,
    border: `1px solid ${COLORS.border.subtle}`,
    borderRadius: 6,
    padding: '20px 24px',
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 8,
  } as React.CSSProperties,
  metricLabel: {
    fontFamily: FONT.body,
    fontSize: 12,
    fontWeight: 500,
    color: COLORS.text.secondary,
    letterSpacing: 0.5,
    textTransform: 'uppercase' as const,
    margin: 0,
  } as React.CSSProperties,
  metricValue: {
    fontFamily: FONT.mono,
    fontSize: 36,
    fontWeight: 600,
    color: COLORS.text.primary,
    lineHeight: 1.1,
    margin: 0,
  } as React.CSSProperties,
  metricDelta: (delta: string) => ({
    fontFamily: FONT.mono,
    fontSize: 13,
    fontWeight: 500,
    color: deltaColor(delta),
    margin: 0,
  } as React.CSSProperties),
  citation: {
    fontFamily: FONT.body,
    fontSize: 11,
    color: COLORS.text.muted,
    fontStyle: 'italic' as const,
    marginTop: 4,
    lineHeight: 1.4,
  } as React.CSSProperties,
} as const;

/* ── Metric definitions ───────────────────────────────────── */
interface MetricDef {
  label: string;
  valueKey: keyof ChannelDetailData['performance'];
  deltaKey: keyof ChannelDetailData['performance'];
  citation: (p: ChannelDetailData['performance'], v: ChannelDetailData['verification']) => string;
}

const METRICS: MetricDef[] = [
  {
    label: 'Verified Revenue',
    valueKey: 'revenueFormatted',
    deltaKey: 'revenueDelta',
    citation: (_p, v) =>
      `Source: ${v.transactionCountFormatted} via ${v.revenueSource}`,
  },
  {
    label: 'Ad Spend',
    valueKey: 'spendFormatted',
    deltaKey: 'spendDelta',
    citation: (p) =>
      `Source: Platform-reported spend across ${p.conversionsFormatted} conversions`,
  },
  {
    label: 'ROAS',
    valueKey: 'roasFormatted',
    deltaKey: 'roasDelta',
    citation: (_p, v) =>
      `Source: Verified revenue / reported spend, cross-referenced via ${v.revenueSource}`,
  },
  {
    label: 'Conversions',
    valueKey: 'conversionsFormatted',
    deltaKey: 'conversionsDelta',
    citation: (_p, v) =>
      `Source: ${v.transactionCountFormatted} matched in ${v.revenueSource}`,
  },
];

/* ── Component ────────────────────────────────────────────── */
interface PerformanceMetricsProps {
  performance: ChannelDetailData['performance'];
  verification: ChannelDetailData['verification'];
}

const PerformanceMetrics: React.FC<PerformanceMetricsProps> = ({ performance, verification }) => {
  return (
    <section style={styles.wrapper} aria-labelledby="da2-section-performance">
      {/* Section label bar */}
      <div style={styles.sectionLabel}>
        <span style={styles.sectionNumber}>02</span>
        <span id="da2-section-performance" style={styles.sectionTitle}>Performance Summary</span>
        <div style={styles.dividerLine} aria-hidden="true" />
      </div>

      {/* 2x2 metric grid */}
      <div style={styles.grid}>
        {METRICS.map((metric) => {
          const value = performance[metric.valueKey] as string;
          const delta = performance[metric.deltaKey] as string;
          const cite = metric.citation(performance, verification);

          return (
            <div key={metric.label} style={styles.card}>
              <p style={styles.metricLabel}>{metric.label}</p>
              <p style={styles.metricValue}>{value}</p>
              <p style={styles.metricDelta(delta)}>{delta}</p>
              <p style={styles.citation}>{cite}</p>
            </div>
          );
        })}
      </div>
    </section>
  );
};

export default PerformanceMetrics;
