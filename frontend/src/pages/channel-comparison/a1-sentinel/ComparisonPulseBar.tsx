/**
 * ComparisonPulseBar — A1-SENTINEL Signature Animated SVG
 *
 * Encodes Bayesian posterior distribution width as visual motion.
 * High confidence = barely moves (narrow posterior).
 * Low confidence = pronounced oscillation (wide posterior).
 *
 * This is NOT decoration — the breathing amplitude IS the confidence level.
 */

import React, { useId } from 'react';
import type { ConfidenceTier } from '@/pages/channel-comparison/shared/types';

interface ComparisonPulseBarProps {
  confidence: ConfidenceTier;
  /** Normalized 0–1: where the point estimate sits on the domain */
  pointPosition: number;
  /** Normalized 0–1: where the lower bound sits */
  lowerPosition: number;
  /** Normalized 0–1: where the upper bound sits */
  upperPosition: number;
  /** Pre-formatted labels */
  formatLow?: string;
  formatPoint?: string;
  formatHigh?: string;
  width?: number;
  height?: number;
}

const CONFIDENCE_CONFIG = {
  high: {
    scale: 1.02,
    duration: '4s',
    color: 'rgb(16, 185, 129)',     // emerald-500
    bgColor: 'rgba(16, 185, 129, 0.12)',
    borderColor: 'rgba(16, 185, 129, 0.3)',
  },
  medium: {
    scale: 1.1,
    duration: '2.8s',
    color: 'rgb(245, 158, 11)',     // amber-500
    bgColor: 'rgba(245, 158, 11, 0.12)',
    borderColor: 'rgba(245, 158, 11, 0.3)',
  },
  low: {
    scale: 1.22,
    duration: '2s',
    color: 'rgb(239, 68, 68)',      // red-500
    bgColor: 'rgba(239, 68, 68, 0.12)',
    borderColor: 'rgba(239, 68, 68, 0.3)',
  },
} as const;

export const ComparisonPulseBar: React.FC<ComparisonPulseBarProps> = ({
  confidence,
  pointPosition,
  lowerPosition,
  upperPosition,
  formatLow,
  formatPoint,
  formatHigh,
  width = 160,
  height = 28,
}) => {
  const id = useId();
  const config = CONFIDENCE_CONFIG[confidence];

  const padX = 8;
  const trackW = width - padX * 2;
  const trackY = height * 0.45;

  const pxPoint = padX + pointPosition * trackW;
  const pxLow = padX + lowerPosition * trackW;
  const pxHigh = padX + upperPosition * trackW;
  const rangeW = pxHigh - pxLow;

  const gradId = `pulse-grad-${id}`;
  const animName = `sentinel-breathe-${id.replace(/:/g, '')}`;

  return (
    <>
      <style>{`
        @keyframes ${animName} {
          from { transform: scaleX(1); opacity: 0.5; }
          to { transform: scaleX(${config.scale}); opacity: 0.85; }
        }
        @media (prefers-reduced-motion: reduce) {
          .sentinel-pulse-range { animation: none !important; }
        }
      `}</style>
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        xmlns="http://www.w3.org/2000/svg"
        aria-label={`Confidence interval: ${formatLow ?? ''} to ${formatHigh ?? ''}, estimate ${formatPoint ?? ''}`}
        role="img"
        style={{ display: 'block' }}
      >
        <defs>
          <linearGradient id={gradId} x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor={config.color} stopOpacity={0} />
            <stop offset="30%" stopColor={config.color} stopOpacity={0.25} />
            <stop offset="50%" stopColor={config.color} stopOpacity={0.4} />
            <stop offset="70%" stopColor={config.color} stopOpacity={0.25} />
            <stop offset="100%" stopColor={config.color} stopOpacity={0} />
          </linearGradient>
        </defs>

        {/* Track baseline */}
        <rect
          x={padX}
          y={trackY - 0.5}
          width={trackW}
          height={1}
          rx={0.5}
          fill="currentColor"
          opacity={0.1}
        />

        {/* Breathing confidence range */}
        <rect
          className="sentinel-pulse-range"
          x={pxLow}
          y={trackY - 6}
          width={rangeW}
          height={12}
          rx={2}
          fill={`url(#${gradId})`}
          style={{
            animation: `${animName} ${config.duration} cubic-bezier(0.45,0,0.55,1) infinite alternate`,
            transformOrigin: `${pxPoint}px ${trackY}px`,
          }}
        />

        {/* Bound tick marks */}
        <line x1={pxLow} y1={trackY - 5} x2={pxLow} y2={trackY + 5} stroke={config.color} strokeWidth={1} strokeOpacity={0.4} />
        <line x1={pxHigh} y1={trackY - 5} x2={pxHigh} y2={trackY + 5} stroke={config.color} strokeWidth={1} strokeOpacity={0.4} />

        {/* Point estimate dot */}
        <circle cx={pxPoint} cy={trackY} r={3} fill={config.color} />
        <circle cx={pxPoint} cy={trackY} r={1.2} fill="white" />

        {/* Labels */}
        {formatLow && (
          <text x={pxLow} y={height - 1} textAnchor="middle" fontSize={7} fill={config.color} opacity={0.6} fontFamily="monospace">
            {formatLow}
          </text>
        )}
        {formatHigh && (
          <text x={pxHigh} y={height - 1} textAnchor="middle" fontSize={7} fill={config.color} opacity={0.6} fontFamily="monospace">
            {formatHigh}
          </text>
        )}
      </svg>
    </>
  );
};
