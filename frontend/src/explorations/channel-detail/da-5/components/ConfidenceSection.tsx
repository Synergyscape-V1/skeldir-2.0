/**
 * DA-5 COMPACT — Confidence section (expandable)
 *
 * Collapsed: "High Confidence +/-10%" one-liner
 * Expanded: range bar with breathing animation, explanation, days/conversions, margin
 */

import React from 'react';
import type { ChannelDetailData } from '../../shared/types';

/* ── Design tokens ─────────────────────────────────────────────── */
const T = {
  textPrimary: '#F0F4FF',
  textSecondary: '#8B9AB8',
  textMuted: '#4A5568',
  high: '#10D98C',
  medium: '#F5A623',
  low: '#F04E4E',
  nested: '#1F2937',
  borderSubtle: 'rgba(139,154,184,0.12)',
  fontBody: "'IBM Plex Sans', sans-serif",
  fontData: "'IBM Plex Mono', monospace",
  breathe: '3000ms',
};

const CONFIDENCE_COLORS: Record<string, string> = {
  high: T.high,
  medium: T.medium,
  low: T.low,
};

const CONFIDENCE_LABELS: Record<string, string> = {
  high: 'High Confidence',
  medium: 'Medium Confidence',
  low: 'Low Confidence',
};

interface ConfidenceSectionProps {
  confidenceRange: ChannelDetailData['confidenceRange'];
}

export const ConfidenceSection: React.FC<ConfidenceSectionProps> = ({
  confidenceRange,
}) => {
  const color = CONFIDENCE_COLORS[confidenceRange.level] || T.textSecondary;

  /* Range bar calculations */
  const rangeSpan = confidenceRange.high - confidenceRange.low;
  const fullWidth = rangeSpan > 0 ? rangeSpan : 1;
  const pointPosition = rangeSpan > 0
    ? ((confidenceRange.point - confidenceRange.low) / fullWidth) * 100
    : 50;

  return (
    <div style={{ padding: '16px 0' }}>
      <style>{`
        @keyframes da5-breathe {
          0%, 100% { opacity: 0.7; }
          50% { opacity: 1; }
        }
        @media (prefers-reduced-motion: reduce) {
          .da5-range-bar { animation: none !important; opacity: 1 !important; }
        }
      `}</style>

      {/* Summary line */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          marginBottom: 20,
        }}
      >
        <span
          style={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: color,
            flexShrink: 0,
          }}
        />
        <span
          style={{
            fontFamily: T.fontBody,
            fontSize: 14,
            fontWeight: 500,
            color: T.textPrimary,
          }}
        >
          {CONFIDENCE_LABELS[confidenceRange.level]}
        </span>
        <span
          style={{
            fontFamily: T.fontData,
            fontSize: 13,
            fontWeight: 400,
            color: T.textSecondary,
          }}
        >
          {'\u00B1'}{confidenceRange.margin}%
        </span>
      </div>

      {/* Range bar */}
      <div
        style={{
          position: 'relative',
          height: 8,
          borderRadius: 4,
          background: T.borderSubtle,
          marginBottom: 12,
        }}
      >
        <div
          className="da5-range-bar"
          style={{
            position: 'absolute',
            top: 0,
            left: '10%',
            right: '10%',
            height: '100%',
            borderRadius: 4,
            background: color,
            opacity: 0.7,
            animation: `da5-breathe ${T.breathe} ease-in-out infinite`,
          }}
        />
        {/* Point estimate marker */}
        <div
          style={{
            position: 'absolute',
            top: '50%',
            left: `calc(10% + ${pointPosition}% * 0.8)`,
            transform: 'translate(-50%, -50%)',
            width: 14,
            height: 14,
            borderRadius: '50%',
            background: color,
            border: `2px solid ${T.nested}`,
            zIndex: 1,
          }}
        />
      </div>

      {/* Range labels */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginBottom: 20,
        }}
      >
        <span
          style={{
            fontFamily: T.fontData,
            fontSize: 12,
            color: T.textSecondary,
          }}
        >
          {confidenceRange.lowFormatted}
        </span>
        <span
          style={{
            fontFamily: T.fontData,
            fontSize: 13,
            fontWeight: 600,
            color: T.textPrimary,
          }}
        >
          {confidenceRange.pointFormatted}
        </span>
        <span
          style={{
            fontFamily: T.fontData,
            fontSize: 12,
            color: T.textSecondary,
          }}
        >
          {confidenceRange.highFormatted}
        </span>
      </div>

      {/* Explanation */}
      <p
        style={{
          fontFamily: T.fontBody,
          fontSize: 13,
          lineHeight: 1.6,
          color: T.textSecondary,
          margin: '0 0 16px',
        }}
      >
        {confidenceRange.explanation}
      </p>

      {/* Stats row */}
      <div
        style={{
          display: 'flex',
          gap: 24,
          flexWrap: 'wrap',
        }}
      >
        <div>
          <span
            style={{
              fontFamily: T.fontBody,
              fontSize: 11,
              color: T.textMuted,
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
            }}
          >
            Days of data
          </span>
          <p
            style={{
              fontFamily: T.fontData,
              fontSize: 14,
              fontWeight: 500,
              color: T.textPrimary,
              margin: '2px 0 0',
            }}
          >
            {confidenceRange.daysOfData}
          </p>
        </div>
        <div>
          <span
            style={{
              fontFamily: T.fontBody,
              fontSize: 11,
              color: T.textMuted,
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
            }}
          >
            Conversions used
          </span>
          <p
            style={{
              fontFamily: T.fontData,
              fontSize: 14,
              fontWeight: 500,
              color: T.textPrimary,
              margin: '2px 0 0',
            }}
          >
            {confidenceRange.conversionsUsed.toLocaleString()}
          </p>
        </div>
        <div>
          <span
            style={{
              fontFamily: T.fontBody,
              fontSize: 11,
              color: T.textMuted,
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
            }}
          >
            Margin
          </span>
          <p
            style={{
              fontFamily: T.fontData,
              fontSize: 14,
              fontWeight: 500,
              color: T.textPrimary,
              margin: '2px 0 0',
            }}
          >
            {'\u00B1'}{confidenceRange.margin}%
          </p>
        </div>
      </div>
    </div>
  );
};
