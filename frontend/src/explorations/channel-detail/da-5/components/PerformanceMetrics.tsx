/**
 * DA-5 COMPACT — Performance metrics
 *
 * Two modes:
 * - hero: 3 large centered numbers (ROAS, Revenue, Spend) above fold
 * - expanded: Full grid with Conversions and CPA
 */

import React from 'react';
import type { ChannelDetailData } from '../../shared/types';

/* ── Design tokens ─────────────────────────────────────────────── */
const T = {
  textPrimary: '#F0F4FF',
  textSecondary: '#8B9AB8',
  high: '#10D98C',
  low: '#F04E4E',
  fontBody: "'IBM Plex Sans', sans-serif",
  fontData: "'IBM Plex Mono', monospace",
  short: '200ms',
};

interface PerformanceMetricsProps {
  performance: ChannelDetailData['performance'];
  mode: 'hero' | 'expanded';
}

/** Parse delta string to determine positive/negative/neutral color */
function deltaColor(delta: string): string {
  if (delta.startsWith('+')) return T.high;
  if (delta.startsWith('-')) return T.low;
  return T.textSecondary;
}

interface MetricCardProps {
  label: string;
  value: string;
  delta: string;
  large: boolean;
}

const MetricCard: React.FC<MetricCardProps> = ({ label, value, delta, large }) => (
  <div
    style={{
      textAlign: 'center',
      padding: large ? '0 16px' : '12px',
    }}
  >
    <p
      style={{
        fontFamily: T.fontBody,
        fontSize: 12,
        fontWeight: 400,
        color: T.textSecondary,
        margin: 0,
        lineHeight: 1.4,
        textTransform: 'uppercase',
        letterSpacing: '0.05em',
      }}
    >
      {label}
    </p>
    <p
      style={{
        fontFamily: T.fontData,
        fontSize: large ? 36 : 24,
        fontWeight: 600,
        color: T.textPrimary,
        margin: '4px 0 0',
        lineHeight: 1.1,
        letterSpacing: '-0.02em',
      }}
    >
      {value}
    </p>
    <p
      style={{
        fontFamily: T.fontData,
        fontSize: 12,
        fontWeight: 400,
        color: deltaColor(delta),
        margin: '6px 0 0',
        lineHeight: 1.4,
      }}
    >
      {delta}
    </p>
  </div>
);

export const PerformanceMetrics: React.FC<PerformanceMetricsProps> = ({
  performance,
  mode,
}) => {
  const heroMetrics = [
    { label: 'ROAS', value: performance.roasFormatted, delta: performance.roasDelta },
    { label: 'Revenue', value: performance.revenueFormatted, delta: performance.revenueDelta },
    { label: 'Spend', value: performance.spendFormatted, delta: performance.spendDelta },
  ];

  const expandedMetrics = [
    { label: 'ROAS', value: performance.roasFormatted, delta: performance.roasDelta },
    { label: 'Revenue', value: performance.revenueFormatted, delta: performance.revenueDelta },
    { label: 'Spend', value: performance.spendFormatted, delta: performance.spendDelta },
    { label: 'Conversions', value: performance.conversionsFormatted, delta: performance.conversionsDelta },
    { label: 'CPA', value: performance.cpaFormatted, delta: performance.cpaDelta },
  ];

  if (mode === 'hero') {
    return (
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'flex-start',
          gap: 32,
          padding: '24px 0 32px',
          flexWrap: 'wrap',
        }}
      >
        {heroMetrics.map((m) => (
          <MetricCard key={m.label} label={m.label} value={m.value} delta={m.delta} large />
        ))}
      </div>
    );
  }

  /* Expanded grid */
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
        gap: 16,
        padding: '16px 0',
      }}
    >
      {expandedMetrics.map((m) => (
        <MetricCard key={m.label} label={m.label} value={m.value} delta={m.delta} large={false} />
      ))}
    </div>
  );
};
