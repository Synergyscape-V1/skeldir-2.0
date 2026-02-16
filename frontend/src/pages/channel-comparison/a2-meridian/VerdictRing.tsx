/**
 * VerdictRing — Animated SVG Circular Confidence Gauge
 *
 * The signature trust mechanism for A2-MERIDIAN.
 * A circular arc fills proportionally to the recommendation confidence level:
 *   - High: ~90% fill, emerald, 4s gentle pulse
 *   - Medium: ~60% fill, amber, 2.8s moderate pulse
 *   - Low: ~35% fill, red, 2s faster pulse
 *
 * Center text displays the recommendation summary.
 * Respects prefers-reduced-motion. Includes aria-label for accessibility.
 */

import React from 'react';
import { cn } from '@/lib/utils';
import type { ConfidenceTier } from '@/pages/channel-comparison/shared/types';

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

interface RingConfig {
  /** Fraction of the ring to fill (0..1) */
  fill: number;
  /** Tailwind stroke color class */
  strokeClass: string;
  /** Raw hex for SVG gradient stop (Tailwind can't reach here) */
  gradientStart: string;
  gradientEnd: string;
  /** Pulse animation duration */
  pulseDuration: string;
  /** Label */
  label: string;
  /** Glow filter color */
  glowColor: string;
}

const RING_CONFIGS: Record<ConfidenceTier, RingConfig> = {
  high: {
    fill: 0.88,
    strokeClass: 'stroke-emerald-400',
    gradientStart: '#34d399',
    gradientEnd: '#10b981',
    pulseDuration: '4s',
    label: 'High Confidence',
    glowColor: '#34d39940',
  },
  medium: {
    fill: 0.6,
    strokeClass: 'stroke-amber-400',
    gradientStart: '#fbbf24',
    gradientEnd: '#f59e0b',
    pulseDuration: '2.8s',
    label: 'Medium Confidence',
    glowColor: '#fbbf2440',
  },
  low: {
    fill: 0.35,
    strokeClass: 'stroke-red-400',
    gradientStart: '#f87171',
    gradientEnd: '#ef4444',
    pulseDuration: '2s',
    label: 'Low Confidence',
    glowColor: '#f8717140',
  },
};

// ---------------------------------------------------------------------------
// Geometry constants
// ---------------------------------------------------------------------------

const SIZE = 200;
const CENTER = SIZE / 2;
const RADIUS = 80;
const STROKE_WIDTH = 10;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

// The arc starts at the top (12 o'clock) — rotate -90deg in the SVG transform
const GAP = 0.04; // 4% gap at the bottom so the ring never looks fully closed

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export interface VerdictRingProps {
  confidence: ConfidenceTier;
  /** Short summary to display in the center of the ring */
  summary?: string;
  /** Optional expected impact line */
  expectedImpact?: string;
  className?: string;
}

export const VerdictRing: React.FC<VerdictRingProps> = ({
  confidence,
  summary,
  expectedImpact,
  className,
}) => {
  const config = RING_CONFIGS[confidence];
  const filledLength = CIRCUMFERENCE * config.fill * (1 - GAP);
  const emptyLength = CIRCUMFERENCE - filledLength;
  const trackLength = CIRCUMFERENCE * (1 - GAP);
  const trackGap = CIRCUMFERENCE * GAP;

  const gradientId = `verdict-gradient-${confidence}`;
  const glowId = `verdict-glow-${confidence}`;

  return (
    <div
      className={cn('flex flex-col items-center', className)}
      aria-label={`Verdict confidence: ${config.label}${summary ? `. ${summary}` : ''}`}
      role="figure"
    >
      <svg
        width={SIZE}
        height={SIZE}
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        className="verdict-ring"
        aria-hidden="true"
      >
        <defs>
          <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor={config.gradientStart} />
            <stop offset="100%" stopColor={config.gradientEnd} />
          </linearGradient>
          <filter id={glowId}>
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feFlood floodColor={config.glowColor} result="color" />
            <feComposite in="color" in2="blur" operator="in" result="glow" />
            <feMerge>
              <feMergeNode in="glow" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Background track */}
        <circle
          cx={CENTER}
          cy={CENTER}
          r={RADIUS}
          fill="none"
          className="stroke-muted/40"
          strokeWidth={STROKE_WIDTH}
          strokeDasharray={`${trackLength} ${trackGap}`}
          strokeLinecap="round"
          transform={`rotate(-90 ${CENTER} ${CENTER})`}
        />

        {/* Filled arc */}
        <circle
          cx={CENTER}
          cy={CENTER}
          r={RADIUS}
          fill="none"
          stroke={`url(#${gradientId})`}
          strokeWidth={STROKE_WIDTH}
          strokeDasharray={`${filledLength} ${emptyLength}`}
          strokeLinecap="round"
          transform={`rotate(-90 ${CENTER} ${CENTER})`}
          filter={`url(#${glowId})`}
          className="verdict-ring__arc"
          style={{
            transition: 'stroke-dasharray 0.8s ease-out',
          }}
        />

        {/* Animated pulse overlay (respects prefers-reduced-motion via CSS) */}
        <circle
          cx={CENTER}
          cy={CENTER}
          r={RADIUS}
          fill="none"
          stroke={`url(#${gradientId})`}
          strokeWidth={STROKE_WIDTH}
          strokeDasharray={`${filledLength} ${emptyLength}`}
          strokeLinecap="round"
          transform={`rotate(-90 ${CENTER} ${CENTER})`}
          className="verdict-ring__pulse"
          style={{
            animationDuration: config.pulseDuration,
          }}
          opacity="0"
        />

        {/* Center text */}
        {summary && (
          <foreignObject
            x={CENTER - 60}
            y={CENTER - 35}
            width={120}
            height={70}
          >
            <div className="flex flex-col items-center justify-center h-full text-center px-1">
              <span className="text-[11px] font-sans font-semibold text-foreground leading-tight line-clamp-3">
                {summary}
              </span>
              {expectedImpact && (
                <span className="text-[10px] font-mono text-muted-foreground mt-1 leading-tight">
                  {expectedImpact}
                </span>
              )}
            </div>
          </foreignObject>
        )}
      </svg>

      {/* Confidence label below the ring */}
      <span
        className={cn(
          'mt-2 px-3 py-1 rounded-full text-[11px] font-medium tracking-wide',
          confidence === 'high' && 'bg-emerald-400/10 text-emerald-400',
          confidence === 'medium' && 'bg-amber-400/10 text-amber-400',
          confidence === 'low' && 'bg-red-400/10 text-red-400',
        )}
      >
        {config.label}
      </span>

      {/* Inline styles for animation — keeps everything self-contained */}
      <style>{`
        .verdict-ring__pulse {
          animation: verdict-pulse ease-in-out infinite;
        }
        @keyframes verdict-pulse {
          0%, 100% { opacity: 0; }
          50% { opacity: 0.35; }
        }
        @media (prefers-reduced-motion: reduce) {
          .verdict-ring__pulse {
            animation: none;
            opacity: 0;
          }
          .verdict-ring__arc {
            transition: none;
          }
        }
      `}</style>
    </div>
  );
};
