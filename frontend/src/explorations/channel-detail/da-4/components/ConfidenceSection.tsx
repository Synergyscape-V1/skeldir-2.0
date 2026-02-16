/**
 * DA-4 ANALYST — Confidence Section
 *
 * Displays the confidence assessment with:
 * - Colored confidence badge (dot + "High/Medium/Low Confidence")
 * - Horizontal range bar with low/point/high markers (monospace)
 * - Breathing animation on the range band (3s alternate, CSS keyframes)
 * - Explanation text paragraph
 * - Data quality line: "{daysOfData} days . {conversionsUsed} conversions"
 *
 * Respects prefers-reduced-motion.
 */

import React, { useMemo } from 'react';
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

/* ── Breathing amplitude per level ──────────────────────────────── */
const BREATH_SCALE: Record<ConfidenceLevel, number> = {
  high: 1.04,
  medium: 1.10,
  low: 1.18,
};

/* ── Props ──────────────────────────────────────────────────────── */
interface ConfidenceSectionProps {
  confidenceRange: ChannelDetailData['confidenceRange'];
}

/* ── Component ──────────────────────────────────────────────────── */
export const ConfidenceSection: React.FC<ConfidenceSectionProps> = ({ confidenceRange }) => {
  const {
    low,
    lowFormatted,
    high,
    highFormatted,
    point,
    pointFormatted,
    level,
    explanation,
    daysOfData,
    conversionsUsed,
  } = confidenceRange;

  const color = tokens.confidence[level];
  const label = CONFIDENCE_LABELS[level];
  const breatheScale = BREATH_SCALE[level];

  /* SVG coordinate mapping */
  const svgW = 400;
  const svgH = 64;
  const padX = 48;
  const barY = 26;
  const barH = 12;
  const range = high - low;
  const visualPad = range * 0.3;
  const domainMin = low - visualPad;
  const domainMax = high + visualPad;
  const domainRange = domainMax - domainMin;

  const toX = (v: number) => padX + ((v - domainMin) / domainRange) * (svgW - 2 * padX);

  const xLow = useMemo(() => toX(low), [low, domainMin, domainRange]);
  const xHigh = useMemo(() => toX(high), [high, domainMin, domainRange]);
  const xPoint = useMemo(() => toX(point), [point, domainMin, domainRange]);
  const bandW = xHigh - xLow;

  const animId = useMemo(
    () => `da4-conf-${Math.random().toString(36).slice(2, 8)}`,
    [],
  );

  return (
    <>
      <style>
        {'@import url("https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700&family=IBM+Plex+Sans:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600;700&display=swap");'}
      </style>
      <div
        style={{
          backgroundColor: tokens.bg.card,
          border: `1px solid ${tokens.border.subtle}`,
          borderRadius: '8px',
          padding: '20px',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
        }}
        role="region"
        aria-label="Confidence assessment"
      >
        {/* Badge */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span
            style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              backgroundColor: color,
              flexShrink: 0,
            }}
            aria-hidden="true"
          />
          <span
            style={{
              fontFamily: tokens.font.body,
              fontSize: '14px',
              fontWeight: 600,
              color: color,
            }}
          >
            {label}
          </span>
        </div>

        {/* Range bar SVG */}
        <svg
          viewBox={`0 0 ${svgW} ${svgH}`}
          width="100%"
          role="img"
          aria-label={`Confidence range: ${lowFormatted} to ${highFormatted}, point estimate ${pointFormatted}`}
          style={{ display: 'block' }}
        >
          <style>{`
            @keyframes ${animId}-breathe {
              0%, 100% { transform: scaleX(1); }
              50% { transform: scaleX(${breatheScale}); }
            }
            .${animId}-band {
              transform-origin: ${xPoint}px ${barY + barH / 2}px;
              animation: ${animId}-breathe 3000ms cubic-bezier(0.4,0,0.2,1) alternate infinite;
            }
            @media (prefers-reduced-motion: reduce) {
              .${animId}-band {
                animation: none !important;
              }
            }
          `}</style>

          {/* Track */}
          <line
            x1={padX}
            y1={barY + barH / 2}
            x2={svgW - padX}
            y2={barY + barH / 2}
            stroke={tokens.border.subtle}
            strokeWidth={1}
          />

          {/* Confidence band (breathes) */}
          <rect
            className={`${animId}-band`}
            x={xLow}
            y={barY}
            width={bandW}
            height={barH}
            rx={barH / 2}
            fill={color}
            opacity={0.22}
          />

          {/* Inner solid bar */}
          <rect
            x={xLow + bandW * 0.12}
            y={barY + 2}
            width={bandW * 0.76}
            height={barH - 4}
            rx={(barH - 4) / 2}
            fill={color}
            opacity={0.40}
          />

          {/* Point estimate dot */}
          <circle cx={xPoint} cy={barY + barH / 2} r={5} fill={color} />
          <circle cx={xPoint} cy={barY + barH / 2} r={2.5} fill={tokens.bg.card} />

          {/* Low label */}
          <text
            x={xLow}
            y={barY - 8}
            textAnchor="middle"
            fill={tokens.text.muted}
            fontFamily={tokens.font.mono}
            fontSize={11}
            fontWeight={400}
          >
            {lowFormatted}
          </text>

          {/* High label */}
          <text
            x={xHigh}
            y={barY - 8}
            textAnchor="middle"
            fill={tokens.text.muted}
            fontFamily={tokens.font.mono}
            fontSize={11}
            fontWeight={400}
          >
            {highFormatted}
          </text>

          {/* Point label */}
          <text
            x={xPoint}
            y={barY + barH + 16}
            textAnchor="middle"
            fill={tokens.text.primary}
            fontFamily={tokens.font.mono}
            fontSize={13}
            fontWeight={600}
          >
            {pointFormatted}
          </text>
        </svg>

        {/* Explanation */}
        <p
          style={{
            fontFamily: tokens.font.body,
            fontSize: '13px',
            fontWeight: 400,
            color: tokens.text.secondary,
            lineHeight: 1.55,
            margin: 0,
          }}
        >
          {explanation}
        </p>

        {/* Data quality line */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            paddingTop: '4px',
            borderTop: `1px solid ${tokens.border.subtle}`,
          }}
        >
          <span
            style={{
              fontFamily: tokens.font.mono,
              fontSize: '12px',
              fontWeight: 500,
              color: tokens.text.muted,
            }}
          >
            {daysOfData} days
          </span>
          <span
            style={{
              fontFamily: tokens.font.mono,
              fontSize: '12px',
              color: tokens.text.muted,
            }}
          >
            &middot;
          </span>
          <span
            style={{
              fontFamily: tokens.font.mono,
              fontSize: '12px',
              fontWeight: 500,
              color: tokens.text.muted,
            }}
          >
            {conversionsUsed.toLocaleString()} conversions
          </span>
        </div>
      </div>
    </>
  );
};

export default ConfidenceSection;
