/**
 * DA-1 COCKPIT — Performance Metrics Instrument Panel
 *
 * Four metric cards in a row, each styled as a cockpit instrument gauge.
 * Each card has a breathing confidence glow halo on its border.
 *
 * Layout: 4-column grid on desktop, 2-column on tablet, 1-column on mobile.
 * All values pre-formatted from ChannelDetailData.performance.
 */

import React, { useId } from 'react';
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
    body: "'IBM Plex Sans', sans-serif",
    mono: "'IBM Plex Mono', monospace",
  },
} as const;

/* ── Helpers ─────────────────────────────────────────────────────── */

function getConfidenceColor(level: ConfidenceLevel): string {
  return tokens.confidence[level];
}

function isDeltaPositive(delta: string): boolean {
  return delta.startsWith('+');
}

function isDeltaNegative(delta: string): boolean {
  return delta.startsWith('-');
}

function getDeltaColor(delta: string, invertLogic = false): string {
  const positive = isDeltaPositive(delta);
  const negative = isDeltaNegative(delta);
  if (invertLogic) {
    if (positive) return tokens.confidence.low;
    if (negative) return tokens.confidence.high;
  } else {
    if (positive) return tokens.confidence.high;
    if (negative) return tokens.confidence.low;
  }
  return tokens.text.secondary;
}

/* ── Types ───────────────────────────────────────────────────────── */

interface MetricCardDef {
  label: string;
  value: string;
  delta: string;
  /** True if a negative delta is actually good (e.g., CPA going down) */
  invertDelta?: boolean;
}

interface PerformanceMetricsProps {
  performance: ChannelDetailData['performance'];
  confidenceLevel: ConfidenceLevel;
}

/* ── Keyframes injected once ─────────────────────────────────────── */

const KEYFRAMES_ID = 'da1-metric-breathe';

function ensureKeyframes() {
  if (typeof document === 'undefined') return;
  if (document.getElementById(KEYFRAMES_ID)) return;

  const style = document.createElement('style');
  style.id = KEYFRAMES_ID;
  style.textContent = `
    @keyframes da1MetricBreathe {
      0%, 100% { box-shadow: 0 0 4px var(--glow-color), inset 0 0 2px var(--glow-color); }
      50% { box-shadow: 0 0 16px var(--glow-color), inset 0 0 6px var(--glow-color); }
    }
    @media (prefers-reduced-motion: reduce) {
      .da1-metric-card {
        animation: none !important;
      }
    }
  `;
  document.head.appendChild(style);
}

/* ── Single Metric Card ──────────────────────────────────────────── */

const MetricCard: React.FC<MetricCardDef & { glowColor: string }> = ({
  label,
  value,
  delta,
  invertDelta,
  glowColor,
}) => {
  React.useEffect(() => {
    ensureKeyframes();
  }, []);

  const deltaColor = getDeltaColor(delta, invertDelta);

  return (
    <div
      className="da1-metric-card"
      style={{
        '--glow-color': `${glowColor}40`,
        padding: '20px',
        background: tokens.bg.card,
        borderRadius: '8px',
        border: `1px solid ${glowColor}30`,
        animation: 'da1MetricBreathe 3000ms ease-in-out alternate infinite',
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
        minWidth: 0,
      } as React.CSSProperties}
    >
      {/* Label */}
      <span
        style={{
          fontFamily: tokens.font.body,
          fontSize: '14px',
          fontWeight: 500,
          color: tokens.text.secondary,
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          lineHeight: 1,
        }}
      >
        {label}
      </span>

      {/* Value */}
      <span
        style={{
          fontFamily: tokens.font.mono,
          fontSize: '36px',
          fontWeight: 600,
          color: tokens.text.primary,
          lineHeight: 1.1,
          letterSpacing: '-0.02em',
        }}
      >
        {value}
      </span>

      {/* Delta */}
      <span
        style={{
          fontFamily: tokens.font.mono,
          fontSize: '12px',
          fontWeight: 400,
          color: deltaColor,
          lineHeight: 1,
        }}
      >
        {delta}
      </span>
    </div>
  );
};

/* ── Main Component ──────────────────────────────────────────────── */

export const PerformanceMetrics: React.FC<PerformanceMetricsProps> = ({
  performance,
  confidenceLevel,
}) => {
  const glowColor = getConfidenceColor(confidenceLevel);
  const sectionId = useId();

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
      invertDelta: true,
    },
    {
      label: 'Conversions',
      value: performance.conversionsFormatted,
      delta: performance.conversionsDelta,
    },
  ];

  return (
    <section aria-labelledby={sectionId}>
      <h2 id={sectionId} className="sr-only" style={{ position: 'absolute', width: '1px', height: '1px', overflow: 'hidden', clip: 'rect(0,0,0,0)', whiteSpace: 'nowrap' }}>
        Performance Metrics
      </h2>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: '16px',
        }}
      >
        {metrics.map((metric) => (
          <MetricCard
            key={metric.label}
            {...metric}
            glowColor={glowColor}
          />
        ))}
      </div>

      {/* Responsive override: inject media query for smaller screens */}
      <style>{`
        @media (max-width: 1024px) {
          [aria-labelledby="${CSS.escape(sectionId)}"] > div {
            grid-template-columns: repeat(2, 1fr) !important;
          }
        }
        @media (max-width: 600px) {
          [aria-labelledby="${CSS.escape(sectionId)}"] > div {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </section>
  );
};

export default PerformanceMetrics;
