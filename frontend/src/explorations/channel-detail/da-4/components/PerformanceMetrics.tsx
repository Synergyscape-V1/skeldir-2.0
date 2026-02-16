/**
 * DA-4 ANALYST — Performance Metrics Grid
 *
 * 2x2 grid of metric cards displaying Revenue, ROAS, Spend, and Conversions.
 * Each card shows label, value (monospace), and delta with directional coloring.
 * Clean grid aesthetic, developer-tool density.
 */

import React from 'react';
import type { ChannelDetailData } from '../../shared/types';

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
    low: '#F04E4E',
  },
  border: {
    subtle: 'rgba(139,154,184,0.12)',
  },
  font: {
    body: "'IBM Plex Sans', sans-serif",
    mono: "'IBM Plex Mono', monospace",
  },
  motion: {
    short: '200ms',
    easing: 'cubic-bezier(0.4, 0, 0.2, 1)',
  },
} as const;

/* ── Helper: determine delta color from string prefix ────────── */
function getDeltaColor(delta: string): string {
  if (delta.startsWith('+')) return tokens.confidence.high;
  if (delta.startsWith('-')) {
    // A negative CPA delta is good (cheaper), negative ROAS is bad
    // We rely on the formatted string from the API which encodes intent
    if (delta.includes('$')) return tokens.confidence.high; // e.g. "-$1.20 vs prev period" (CPA down = good)
    return tokens.confidence.low;
  }
  return tokens.text.secondary;
}

/* ── Metric card definition ──────────────────────────────────── */
interface MetricCardDef {
  label: string;
  value: string;
  delta: string;
}

/* ── Props ──────────────────────────────────────────────────────── */
interface PerformanceMetricsProps {
  performance: ChannelDetailData['performance'];
}

/* ── Component ──────────────────────────────────────────────────── */
export const PerformanceMetrics: React.FC<PerformanceMetricsProps> = ({ performance }) => {
  const metrics: MetricCardDef[] = [
    {
      label: 'Revenue',
      value: performance.revenueFormatted,
      delta: performance.revenueDelta,
    },
    {
      label: 'ROAS',
      value: performance.roasFormatted,
      delta: performance.roasDelta,
    },
    {
      label: 'Spend',
      value: performance.spendFormatted,
      delta: performance.spendDelta,
    },
    {
      label: 'Conversions',
      value: performance.conversionsFormatted,
      delta: performance.conversionsDelta,
    },
  ];

  return (
    <>
      <style>
        {'@import url("https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700&family=IBM+Plex+Sans:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600;700&display=swap");'}
      </style>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(2, 1fr)',
          gap: '12px',
        }}
        role="region"
        aria-label="Performance metrics"
      >
        {metrics.map((metric) => {
          const deltaColor = getDeltaColor(metric.delta);
          return (
            <div
              key={metric.label}
              style={{
                backgroundColor: tokens.bg.card,
                border: `1px solid ${tokens.border.subtle}`,
                borderRadius: '8px',
                padding: '16px',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
                transition: `border-color ${tokens.motion.short} ${tokens.motion.easing}`,
              }}
            >
              {/* Label */}
              <span
                style={{
                  fontFamily: tokens.font.body,
                  fontSize: '14px',
                  fontWeight: 400,
                  color: tokens.text.secondary,
                  lineHeight: 1.2,
                }}
              >
                {metric.label}
              </span>

              {/* Value */}
              <span
                style={{
                  fontFamily: tokens.font.mono,
                  fontSize: '24px',
                  fontWeight: 600,
                  color: tokens.text.primary,
                  lineHeight: 1.1,
                  letterSpacing: '-0.02em',
                }}
              >
                {metric.value}
              </span>

              {/* Delta */}
              <span
                style={{
                  fontFamily: tokens.font.mono,
                  fontSize: '12px',
                  fontWeight: 400,
                  color: deltaColor,
                  lineHeight: 1.3,
                }}
              >
                {metric.delta}
              </span>
            </div>
          );
        })}
      </div>
    </>
  );
};

export default PerformanceMetrics;
