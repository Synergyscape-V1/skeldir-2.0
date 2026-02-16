/**
 * DA-2 DOSSIER — Confidence-Band Breathing SVG
 *
 * An animated SVG showing the ROAS confidence interval as a horizontal range bar.
 * The band slowly expands and contracts ("breathes") at a rate proportional to
 * the uncertainty level: high confidence = subtle breath, low = dramatic.
 *
 * Respects prefers-reduced-motion by disabling animation.
 */
import React, { useMemo } from 'react';
import type { ConfidenceLevel } from '../../shared/types';

/* ── Design Tokens ────────────────────────────────────────── */
const COLORS = {
  bg: '#111827',
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
  border: 'rgba(139,154,184,0.12)',
} as const;

const FONT = {
  mono: "'IBM Plex Mono', monospace",
  body: "'IBM Plex Sans', sans-serif",
  heading: "'Syne', sans-serif",
} as const;

/* ── Breathing amplitude per confidence ───────────────────── */
const BREATH_AMPLITUDE: Record<ConfidenceLevel, number> = {
  high: 8,
  medium: 18,
  low: 30,
};

/* ── Component Props ──────────────────────────────────────── */
interface SignatureSVGProps {
  pointFormatted: string;
  lowFormatted: string;
  highFormatted: string;
  point: number;
  low: number;
  high: number;
  level: ConfidenceLevel;
  /** Optional width override — defaults to 100% of parent */
  width?: number | string;
}

const SignatureSVG: React.FC<SignatureSVGProps> = ({
  pointFormatted,
  lowFormatted,
  highFormatted,
  point,
  low,
  high,
  level,
  width = '100%',
}) => {
  const color = COLORS.confidence[level];
  const amplitude = BREATH_AMPLITUDE[level];

  /* Map data values to SVG x-coordinates within a padded viewport */
  const svgWidth = 480;
  const svgHeight = 120;
  const padX = 60;
  const barY = 52;
  const barH = 16;

  const range = high - low;
  const visualPad = range * 0.25; // extra space beyond bounds
  const domainMin = low - visualPad;
  const domainMax = high + visualPad;
  const domainRange = domainMax - domainMin;

  const toX = (val: number) => padX + ((val - domainMin) / domainRange) * (svgWidth - 2 * padX);

  const xLow = useMemo(() => toX(low), [low, domainMin, domainRange]);
  const xHigh = useMemo(() => toX(high), [high, domainMin, domainRange]);
  const xPoint = useMemo(() => toX(point), [point, domainMin, domainRange]);
  const bandWidth = xHigh - xLow;

  /* Unique ID for this instance to avoid SVG id collisions */
  const instanceId = useMemo(
    () => `da2-breath-${Math.random().toString(36).slice(2, 8)}`,
    [],
  );

  const ariaLabel = `Confidence band: ${level} confidence. Point estimate ${pointFormatted}, range ${lowFormatted} to ${highFormatted}.`;

  return (
    <svg
      viewBox={`0 0 ${svgWidth} ${svgHeight}`}
      width={width}
      role="img"
      aria-label={ariaLabel}
      style={{ display: 'block', maxWidth: 480 }}
    >
      {/* ── Reduced-motion & breathing keyframes ───────── */}
      <style>{`
        @keyframes ${instanceId}-breathe {
          0%, 100% {
            transform: scaleX(1);
          }
          50% {
            transform: scaleX(${1 + amplitude / 100});
          }
        }
        .${instanceId}-band {
          transform-origin: ${xPoint}px ${barY + barH / 2}px;
          animation: ${instanceId}-breathe 3000ms cubic-bezier(0.4,0,0.2,1) alternate infinite;
        }
        @media (prefers-reduced-motion: reduce) {
          .${instanceId}-band {
            animation: none !important;
          }
        }
      `}</style>

      {/* ── Center line (track) ────────────────────────── */}
      <line
        x1={padX}
        y1={barY + barH / 2}
        x2={svgWidth - padX}
        y2={barY + barH / 2}
        stroke={COLORS.border}
        strokeWidth={1}
      />

      {/* ── Confidence band (breathes) ─────────────────── */}
      <rect
        className={`${instanceId}-band`}
        x={xLow}
        y={barY}
        width={bandWidth}
        height={barH}
        rx={barH / 2}
        fill={color}
        opacity={0.25}
      />

      {/* ── Solid inner bar (narrower, static) ─────────── */}
      <rect
        x={xLow + bandWidth * 0.15}
        y={barY + 3}
        width={bandWidth * 0.7}
        height={barH - 6}
        rx={(barH - 6) / 2}
        fill={color}
        opacity={0.45}
      />

      {/* ── Point estimate dot ─────────────────────────── */}
      <circle
        cx={xPoint}
        cy={barY + barH / 2}
        r={6}
        fill={color}
      />
      <circle
        cx={xPoint}
        cy={barY + barH / 2}
        r={3}
        fill={COLORS.bg}
      />

      {/* ── Low bound label ────────────────────────────── */}
      <text
        x={xLow}
        y={barY - 10}
        textAnchor="middle"
        fill={COLORS.text.secondary}
        fontFamily={FONT.mono}
        fontSize={12}
        fontWeight={500}
      >
        {lowFormatted}
      </text>

      {/* ── High bound label ───────────────────────────── */}
      <text
        x={xHigh}
        y={barY - 10}
        textAnchor="middle"
        fill={COLORS.text.secondary}
        fontFamily={FONT.mono}
        fontSize={12}
        fontWeight={500}
      >
        {highFormatted}
      </text>

      {/* ── Point estimate label ───────────────────────── */}
      <text
        x={xPoint}
        y={barY + barH + 22}
        textAnchor="middle"
        fill={COLORS.text.primary}
        fontFamily={FONT.mono}
        fontSize={14}
        fontWeight={600}
      >
        {pointFormatted}
      </text>

      {/* ── Confidence level label ─────────────────────── */}
      <text
        x={xPoint}
        y={barY + barH + 40}
        textAnchor="middle"
        fill={color}
        fontFamily={FONT.body}
        fontSize={11}
        fontWeight={500}
        letterSpacing={1}
      >
        {level.toUpperCase()} CONFIDENCE
      </text>
    </svg>
  );
};

export default SignatureSVG;
