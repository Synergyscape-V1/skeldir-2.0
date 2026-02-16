/**
 * DA-1 COCKPIT — Confidence Section
 *
 * ROAS confidence range instrument panel:
 * - Point estimate prominently displayed
 * - Range bar showing low-high with breathing animation
 * - Confidence level badge (High/Medium/Low with color)
 * - Explanation text
 * - Bound labels in IBM Plex Mono
 *
 * All values pre-formatted. No client-side calculations.
 */

import React, { useEffect, useId } from 'react';
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

const CONFIDENCE_LABELS: Record<ConfidenceLevel, string> = {
  high: 'High Confidence',
  medium: 'Medium Confidence',
  low: 'Low Confidence',
};

/* ── Keyframes ───────────────────────────────────────────────────── */

const KEYFRAMES_ID = 'da1-confidence-breathe';

function ensureKeyframes() {
  if (typeof document === 'undefined') return;
  if (document.getElementById(KEYFRAMES_ID)) return;

  const style = document.createElement('style');
  style.id = KEYFRAMES_ID;
  style.textContent = `
    @keyframes da1ConfidenceBreathe {
      0%, 100% { opacity: 0.6; filter: blur(0px); }
      50% { opacity: 1; filter: blur(1px); }
    }
    @keyframes da1ConfidencePulse {
      0%, 100% { transform: scale(1); }
      50% { transform: scale(1.08); }
    }
    @media (prefers-reduced-motion: reduce) {
      .da1-conf-bar, .da1-conf-point {
        animation: none !important;
      }
    }
  `;
  document.head.appendChild(style);
}

interface ConfidenceSectionProps {
  confidenceRange: ChannelDetailData['confidenceRange'];
}

export const ConfidenceSection: React.FC<ConfidenceSectionProps> = ({
  confidenceRange,
}) => {
  const sectionId = useId();
  const confColor = tokens.confidence[confidenceRange.level];

  useEffect(() => {
    ensureKeyframes();
  }, []);

  // Position the point estimate on the range bar (0–100%)
  const rangeSpan = confidenceRange.high - confidenceRange.low;
  const pointPosition = rangeSpan > 0
    ? ((confidenceRange.point - confidenceRange.low) / rangeSpan) * 100
    : 50;

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
        gap: '20px',
      }}
    >
      {/* Header row */}
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
          ROAS Confidence Range
        </h3>

        {/* Confidence badge */}
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            padding: '4px 14px',
            borderRadius: '9999px',
            backgroundColor: `${confColor}18`,
            border: `1px solid ${confColor}40`,
            fontFamily: tokens.font.body,
            fontSize: '12px',
            fontWeight: 600,
            color: confColor,
          }}
        >
          <span
            aria-hidden="true"
            style={{
              width: '6px',
              height: '6px',
              borderRadius: '50%',
              backgroundColor: confColor,
            }}
          />
          {CONFIDENCE_LABELS[confidenceRange.level]}
        </span>
      </div>

      {/* Point estimate hero */}
      <div
        style={{
          display: 'flex',
          alignItems: 'baseline',
          gap: '12px',
        }}
      >
        <span
          className="da1-conf-point"
          style={{
            fontFamily: tokens.font.mono,
            fontSize: '36px',
            fontWeight: 600,
            color: tokens.text.primary,
            lineHeight: 1,
            animation: 'da1ConfidencePulse 3000ms ease-in-out alternate infinite',
          }}
        >
          {confidenceRange.pointFormatted}
        </span>
        <span
          style={{
            fontFamily: tokens.font.mono,
            fontSize: '14px',
            color: tokens.text.secondary,
          }}
        >
          ROAS point estimate
        </span>
      </div>

      {/* Range bar visualization */}
      <div style={{ position: 'relative', padding: '16px 0' }}>
        {/* Track */}
        <div
          style={{
            position: 'relative',
            height: '8px',
            borderRadius: '4px',
            backgroundColor: tokens.bg.nested,
            overflow: 'visible',
          }}
        >
          {/* Filled range */}
          <div
            className="da1-conf-bar"
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              height: '100%',
              borderRadius: '4px',
              background: `linear-gradient(90deg, ${confColor}60, ${confColor}, ${confColor}60)`,
              animation: 'da1ConfidenceBreathe 3000ms ease-in-out alternate infinite',
            }}
          />

          {/* Point estimate marker */}
          <div
            style={{
              position: 'absolute',
              top: '50%',
              left: `${pointPosition}%`,
              transform: 'translate(-50%, -50%)',
              width: '16px',
              height: '16px',
              borderRadius: '50%',
              backgroundColor: confColor,
              border: `2px solid ${tokens.text.primary}`,
              boxShadow: `0 0 12px ${confColor}80`,
              zIndex: 1,
            }}
            role="img"
            aria-label={`Point estimate at ${confidenceRange.pointFormatted}`}
          />
        </div>

        {/* Bound labels */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            marginTop: '12px',
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
            <span
              style={{
                fontFamily: tokens.font.body,
                fontSize: '12px',
                color: tokens.text.muted,
              }}
            >
              Lower bound
            </span>
            <span
              style={{
                fontFamily: tokens.font.mono,
                fontSize: '14px',
                fontWeight: 500,
                color: tokens.text.secondary,
              }}
            >
              {confidenceRange.lowFormatted}
            </span>
          </div>

          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '2px',
              textAlign: 'right',
            }}
          >
            <span
              style={{
                fontFamily: tokens.font.body,
                fontSize: '12px',
                color: tokens.text.muted,
              }}
            >
              Upper bound
            </span>
            <span
              style={{
                fontFamily: tokens.font.mono,
                fontSize: '14px',
                fontWeight: 500,
                color: tokens.text.secondary,
              }}
            >
              {confidenceRange.highFormatted}
            </span>
          </div>
        </div>
      </div>

      {/* Data quality stats */}
      <div
        style={{
          display: 'flex',
          gap: '24px',
          padding: '12px 16px',
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
            Days of data
          </span>
          <span
            style={{
              fontFamily: tokens.font.mono,
              fontSize: '14px',
              fontWeight: 500,
              color: tokens.text.primary,
            }}
          >
            {confidenceRange.daysOfData}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span
            style={{
              fontFamily: tokens.font.body,
              fontSize: '12px',
              color: tokens.text.muted,
            }}
          >
            Conversions used
          </span>
          <span
            style={{
              fontFamily: tokens.font.mono,
              fontSize: '14px',
              fontWeight: 500,
              color: tokens.text.primary,
            }}
          >
            {confidenceRange.conversionsUsed.toLocaleString()}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span
            style={{
              fontFamily: tokens.font.body,
              fontSize: '12px',
              color: tokens.text.muted,
            }}
          >
            Margin
          </span>
          <span
            style={{
              fontFamily: tokens.font.mono,
              fontSize: '14px',
              fontWeight: 500,
              color: tokens.text.primary,
            }}
          >
            {confidenceRange.margin}%
          </span>
        </div>
      </div>

      {/* Explanation */}
      <p
        style={{
          fontFamily: tokens.font.body,
          fontSize: '14px',
          color: tokens.text.secondary,
          margin: 0,
          lineHeight: 1.6,
        }}
      >
        {confidenceRange.explanation}
      </p>
    </section>
  );
};

export default ConfidenceSection;
