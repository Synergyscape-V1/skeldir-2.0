/**
 * DA-3 TIMELINE — Confidence Section
 *
 * Confidence details panel: badge with color dot, range display,
 * breathing range bar animation (CSS only), explanation text,
 * and supporting metrics (days of data, conversion count).
 *
 * All values arrive pre-formatted. No client-side calculations.
 */

import React from 'react';
import type { ChannelDetailData } from '../../shared/types';

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
  border: {
    subtle: 'rgba(139,154,184,0.12)',
    default: 'rgba(139,154,184,0.24)',
  },
  font: {
    heading: "'Syne', sans-serif",
    body: "'IBM Plex Sans', sans-serif",
    mono: "'IBM Plex Mono', monospace",
  },
  motion: {
    breathe: '3000ms',
    short: '200ms',
  },
} as const;

const CONFIDENCE_LABELS: Record<string, string> = {
  high: 'High Confidence',
  medium: 'Medium Confidence',
  low: 'Low Confidence',
};

/* -- Breathing animation keyframes (injected once) ----------------------- */
const breatheKeyframes = `
@keyframes da3-confidence-breathe {
  0%, 100% { transform: scaleX(1); opacity: 0.7; }
  50% { transform: scaleX(1.08); opacity: 1; }
}
@media (prefers-reduced-motion: reduce) {
  .da3-confidence-breathe-bar {
    animation: none !important;
  }
}
`;

/* -- Component ------------------------------------------------------------ */

interface ConfidenceSectionProps {
  confidenceRange: ChannelDetailData['confidenceRange'];
}

export const ConfidenceSection: React.FC<ConfidenceSectionProps> = ({
  confidenceRange,
}) => {
  const levelColor = tokens.confidence[confidenceRange.level];
  const levelLabel = CONFIDENCE_LABELS[confidenceRange.level];

  /* Calculate point position as percentage within the low-high range */
  const rangeSpan = confidenceRange.high - confidenceRange.low;
  const pointPosition = rangeSpan > 0
    ? ((confidenceRange.point - confidenceRange.low) / rangeSpan) * 100
    : 50;

  return (
    <section
      role="region"
      aria-label="Confidence analysis"
      style={{
        background: tokens.bg.card,
        borderRadius: '8px',
        border: `1px solid ${tokens.border.subtle}`,
        padding: '24px',
        display: 'flex',
        flexDirection: 'column',
        gap: '20px',
      }}
    >
      {/* Inject breathing keyframes */}
      <style>{breatheKeyframes}</style>

      {/* Header: Confidence badge */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <div
          aria-hidden="true"
          style={{
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            backgroundColor: levelColor,
            boxShadow: `0 0 8px ${levelColor}50`,
          }}
        />
        <span
          style={{
            fontFamily: tokens.font.heading,
            fontSize: '16px',
            fontWeight: 600,
            color: tokens.text.primary,
          }}
        >
          {levelLabel}
        </span>
      </div>

      {/* Range display: low - point - high */}
      <div
        style={{
          display: 'flex',
          alignItems: 'baseline',
          justifyContent: 'space-between',
          gap: '12px',
        }}
      >
        <span
          style={{
            fontFamily: tokens.font.mono,
            fontSize: '13px',
            color: tokens.text.muted,
          }}
        >
          {confidenceRange.lowFormatted}
        </span>
        <span
          style={{
            fontFamily: tokens.font.mono,
            fontSize: '22px',
            fontWeight: 600,
            color: tokens.text.primary,
          }}
        >
          {confidenceRange.pointFormatted}
        </span>
        <span
          style={{
            fontFamily: tokens.font.mono,
            fontSize: '13px',
            color: tokens.text.muted,
          }}
        >
          {confidenceRange.highFormatted}
        </span>
      </div>

      {/* Breathing range bar */}
      <div
        style={{
          position: 'relative',
          height: '8px',
          borderRadius: '4px',
          background: tokens.bg.nested,
          overflow: 'visible',
        }}
      >
        {/* Confidence band (the breathing river) */}
        <div
          className="da3-confidence-breathe-bar"
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            height: '100%',
            borderRadius: '4px',
            background: `linear-gradient(90deg, ${levelColor}00 0%, ${levelColor}40 20%, ${levelColor}60 50%, ${levelColor}40 80%, ${levelColor}00 100%)`,
            animation: `da3-confidence-breathe ${tokens.motion.breathe} ease-in-out infinite`,
            transformOrigin: 'center',
          }}
        />

        {/* Point estimate marker */}
        <div
          aria-label={`Point estimate: ${confidenceRange.pointFormatted}`}
          style={{
            position: 'absolute',
            top: '-2px',
            left: `${pointPosition}%`,
            transform: 'translateX(-50%)',
            width: '12px',
            height: '12px',
            borderRadius: '50%',
            backgroundColor: levelColor,
            border: `2px solid ${tokens.bg.card}`,
            boxShadow: `0 0 6px ${levelColor}60`,
            zIndex: 1,
          }}
        />
      </div>

      {/* Margin label */}
      <div
        style={{
          textAlign: 'center',
        }}
      >
        <span
          style={{
            fontFamily: tokens.font.mono,
            fontSize: '11px',
            color: tokens.text.muted,
          }}
        >
          {'\u00B1'}{confidenceRange.margin}% margin
        </span>
      </div>

      {/* Explanation */}
      <p
        style={{
          fontFamily: tokens.font.body,
          fontSize: '13px',
          lineHeight: 1.6,
          color: tokens.text.secondary,
          margin: 0,
        }}
      >
        {confidenceRange.explanation}
      </p>

      {/* Supporting metrics row */}
      <div
        style={{
          display: 'flex',
          gap: '16px',
          paddingTop: '12px',
          borderTop: `1px solid ${tokens.border.subtle}`,
        }}
      >
        <div
          style={{
            flex: '1 1 0',
            display: 'flex',
            flexDirection: 'column',
            gap: '2px',
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
            Days of Data
          </span>
          <span
            style={{
              fontFamily: tokens.font.mono,
              fontSize: '18px',
              fontWeight: 600,
              color: tokens.text.primary,
            }}
          >
            {confidenceRange.daysOfData}
          </span>
        </div>

        <div
          aria-hidden="true"
          style={{
            width: '1px',
            alignSelf: 'stretch',
            backgroundColor: tokens.border.subtle,
          }}
        />

        <div
          style={{
            flex: '1 1 0',
            display: 'flex',
            flexDirection: 'column',
            gap: '2px',
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
            Conversions
          </span>
          <span
            style={{
              fontFamily: tokens.font.mono,
              fontSize: '18px',
              fontWeight: 600,
              color: tokens.text.primary,
            }}
          >
            {confidenceRange.conversionsUsed.toLocaleString()}
          </span>
        </div>
      </div>
    </section>
  );
};

export default ConfidenceSection;
