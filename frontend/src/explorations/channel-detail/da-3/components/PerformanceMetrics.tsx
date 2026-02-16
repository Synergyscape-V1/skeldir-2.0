/**
 * DA-3 TIMELINE — Performance Metrics Strip
 *
 * Compact horizontal metric strip above the timeline ribbon.
 * 4 metrics in a row: Revenue, ROAS, Spend, Conversions.
 * Each shows value (IBM Plex Mono, large) + delta (small, colored) + label (small, secondary).
 *
 * Compact so the timeline gets maximum vertical space.
 * All values arrive pre-formatted from ChannelDetailData.
 */

import React from 'react';
import type { ChannelDetailData, ConfidenceLevel } from '../../shared/types';

/* ── Design Tokens ─────────────────────────────────────────────── */
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

/** Determine delta color from the text prefix */
function deltaColor(delta: string): string {
  if (delta.startsWith('+')) return tokens.confidence.high;
  if (delta.startsWith('-')) {
    // Negative CPA is actually good (cost went down)
    if (delta.includes('$')) return tokens.confidence.high;
    return tokens.confidence.low;
  }
  return tokens.text.secondary;
}

interface MetricCardProps {
  label: string;
  value: string;
  delta: string;
  isMono?: boolean;
}

const MetricCard: React.FC<MetricCardProps> = ({ label, value, delta, isMono = true }) => (
  <div
    style={{
      flex: '1 1 0',
      minWidth: '140px',
      padding: '16px 20px',
      display: 'flex',
      flexDirection: 'column',
      gap: '4px',
    }}
  >
    <span
      style={{
        fontFamily: tokens.font.body,
        fontSize: '11px',
        fontWeight: 500,
        color: tokens.text.muted,
        textTransform: 'uppercase',
        letterSpacing: '0.06em',
      }}
    >
      {label}
    </span>
    <span
      style={{
        fontFamily: isMono ? tokens.font.mono : tokens.font.heading,
        fontSize: '24px',
        fontWeight: 600,
        color: tokens.text.primary,
        lineHeight: 1.2,
      }}
    >
      {value}
    </span>
    <span
      style={{
        fontFamily: tokens.font.mono,
        fontSize: '11px',
        fontWeight: 400,
        color: deltaColor(delta),
        lineHeight: 1.3,
      }}
    >
      {delta}
    </span>
  </div>
);

interface PerformanceMetricsProps {
  performance: ChannelDetailData['performance'];
  confidenceLevel: ConfidenceLevel;
}

export const PerformanceMetrics: React.FC<PerformanceMetricsProps> = ({
  performance,
  confidenceLevel,
}) => {
  const confidenceColor = tokens.confidence[confidenceLevel];

  return (
    <div
      role="region"
      aria-label="Channel performance metrics"
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        background: tokens.bg.card,
        borderRadius: '8px',
        border: `1px solid ${tokens.border.subtle}`,
        overflow: 'hidden',
        position: 'relative',
      }}
    >
      {/* Subtle confidence indicator line at top */}
      <div
        aria-hidden="true"
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: '2px',
          background: `linear-gradient(90deg, ${confidenceColor}00 0%, ${confidenceColor}60 30%, ${confidenceColor}60 70%, ${confidenceColor}00 100%)`,
        }}
      />

      <MetricCard
        label="Verified Revenue"
        value={performance.revenueFormatted}
        delta={performance.revenueDelta}
      />

      {/* Vertical separator */}
      <div
        aria-hidden="true"
        style={{
          width: '1px',
          alignSelf: 'stretch',
          margin: '12px 0',
          backgroundColor: tokens.border.subtle,
        }}
      />

      <MetricCard
        label="ROAS"
        value={performance.roasFormatted}
        delta={performance.roasDelta}
      />

      <div
        aria-hidden="true"
        style={{
          width: '1px',
          alignSelf: 'stretch',
          margin: '12px 0',
          backgroundColor: tokens.border.subtle,
        }}
      />

      <MetricCard
        label="Ad Spend"
        value={performance.spendFormatted}
        delta={performance.spendDelta}
      />

      <div
        aria-hidden="true"
        style={{
          width: '1px',
          alignSelf: 'stretch',
          margin: '12px 0',
          backgroundColor: tokens.border.subtle,
        }}
      />

      <MetricCard
        label="Conversions"
        value={performance.conversionsFormatted}
        delta={performance.conversionsDelta}
      />
    </div>
  );
};

export default PerformanceMetrics;
