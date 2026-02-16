/**
 * Final Single Channel Detail — ROAS Confidence Range
 *
 * Based on DA-1 COCKPIT confidence section.
 * Adapted for light theme.
 *
 * Features: Point estimate hero, range bar with breathing animation,
 * confidence badge, bound labels, data quality stats, explanation text.
 */

import React, { useEffect, useId } from 'react';
import type { ChannelDetailData, ConfidenceLevel } from '@/explorations/channel-detail/shared/types';
import { tokens } from '../tokens';

const CONFIDENCE_LABELS: Record<ConfidenceLevel, string> = {
  high: 'High Confidence',
  medium: 'Medium Confidence',
  low: 'Low Confidence',
};

const KEYFRAMES_ID = 'final-confidence-breathe';

function ensureKeyframes() {
  if (typeof document === 'undefined') return;
  if (document.getElementById(KEYFRAMES_ID)) return;

  const style = document.createElement('style');
  style.id = KEYFRAMES_ID;
  style.textContent = `
    @keyframes finalConfidenceBreathe {
      0%, 100% { opacity: 0.6; }
      50% { opacity: 1; }
    }
    @keyframes finalConfidencePulse {
      0%, 100% { transform: scale(1); }
      50% { transform: scale(1.04); }
    }
    @media (prefers-reduced-motion: reduce) {
      .final-conf-bar, .final-conf-point {
        animation: none !important;
      }
    }
  `;
  document.head.appendChild(style);
}

interface ConfidenceSectionProps {
  confidenceRange: ChannelDetailData['confidenceRange'];
}

export const ConfidenceSection: React.FC<ConfidenceSectionProps> = ({ confidenceRange }) => {
  const sectionId = useId();
  const confColor = tokens.confidence[confidenceRange.level];

  useEffect(() => { ensureKeyframes(); }, []);

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
        borderRadius: tokens.radius.md,
        border: `1px solid ${tokens.border.default}`,
        display: 'flex',
        flexDirection: 'column',
        gap: '20px',
        boxShadow: tokens.shadow.sm,
      }}
    >
      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
        <h3 id={sectionId} style={{ fontFamily: tokens.font.heading, fontSize: '20px', fontWeight: 600, color: tokens.text.primary, margin: 0 }}>
          ROAS Confidence Range
        </h3>
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            padding: '4px 14px',
            borderRadius: tokens.radius.pill,
            backgroundColor: `${confColor}12`,
            border: `1px solid ${confColor}30`,
            fontFamily: tokens.font.body,
            fontSize: '12px',
            fontWeight: 600,
            color: confColor,
          }}
        >
          <span aria-hidden="true" style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: confColor }} />
          {CONFIDENCE_LABELS[confidenceRange.level]}
        </span>
      </div>

      {/* Point estimate */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: '12px' }}>
        <span
          className="final-conf-point"
          style={{
            fontFamily: tokens.font.mono,
            fontSize: '36px',
            fontWeight: 600,
            color: tokens.text.primary,
            lineHeight: 1,
            animation: 'finalConfidencePulse 3000ms ease-in-out alternate infinite',
          }}
        >
          {confidenceRange.pointFormatted}
        </span>
        <span style={{ fontFamily: tokens.font.mono, fontSize: '14px', color: tokens.text.secondary }}>
          ROAS point estimate
        </span>
      </div>

      {/* Range bar */}
      <div style={{ position: 'relative', padding: '16px 0' }}>
        <div style={{ position: 'relative', height: '8px', borderRadius: '4px', backgroundColor: tokens.bg.nested, overflow: 'visible' }}>
          <div
            className="final-conf-bar"
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              height: '100%',
              borderRadius: '4px',
              background: `linear-gradient(90deg, ${confColor}40, ${confColor}, ${confColor}40)`,
              animation: 'finalConfidenceBreathe 3000ms ease-in-out alternate infinite',
            }}
          />
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
              border: `3px solid ${tokens.bg.card}`,
              boxShadow: `0 0 0 1px ${confColor}40, 0 2px 6px ${confColor}30`,
              zIndex: 1,
            }}
            role="img"
            aria-label={`Point estimate at ${confidenceRange.pointFormatted}`}
          />
        </div>

        {/* Bound labels */}
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '12px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
            <span style={{ fontFamily: tokens.font.body, fontSize: '12px', color: tokens.text.muted }}>Lower bound</span>
            <span style={{ fontFamily: tokens.font.mono, fontSize: '14px', fontWeight: 500, color: tokens.text.secondary }}>{confidenceRange.lowFormatted}</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', textAlign: 'right' }}>
            <span style={{ fontFamily: tokens.font.body, fontSize: '12px', color: tokens.text.muted }}>Upper bound</span>
            <span style={{ fontFamily: tokens.font.mono, fontSize: '14px', fontWeight: 500, color: tokens.text.secondary }}>{confidenceRange.highFormatted}</span>
          </div>
        </div>
      </div>

      {/* Data quality stats */}
      <div style={{ display: 'flex', gap: '24px', padding: '12px 16px', background: tokens.bg.nested, borderRadius: tokens.radius.sm, flexWrap: 'wrap' }}>
        {[
          { label: 'Days of data', value: String(confidenceRange.daysOfData) },
          { label: 'Conversions used', value: confidenceRange.conversionsUsed.toLocaleString() },
          { label: 'Margin', value: `${confidenceRange.margin}%` },
        ].map(({ label, value }) => (
          <div key={label} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontFamily: tokens.font.body, fontSize: '12px', color: tokens.text.muted }}>{label}</span>
            <span style={{ fontFamily: tokens.font.mono, fontSize: '14px', fontWeight: 500, color: tokens.text.primary }}>{value}</span>
          </div>
        ))}
      </div>

      {/* Explanation */}
      <p style={{ fontFamily: tokens.font.body, fontSize: '14px', color: tokens.text.secondary, margin: 0, lineHeight: 1.6 }}>
        {confidenceRange.explanation}
      </p>
    </section>
  );
};

export default ConfidenceSection;
