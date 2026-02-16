/**
 * RankShiftIndicator — Animated SVG showing channel rank stability
 *
 * Three states derived from TrendDirection:
 * - "stable" (trend === 'stable'): horizontal line + dot, gentle breathing, emerald
 * - "rising" (trend === 'up'): upward arrow with upward motion, emerald
 * - "falling" (trend === 'down'): downward arrow with downward motion, red
 *
 * Respects prefers-reduced-motion. Accessible via aria-label.
 */

import React from 'react';
import type { TrendDirection } from '@/pages/channel-comparison/shared/types';

export interface RankShiftIndicatorProps {
  trend: TrendDirection;
  size?: number;
  className?: string;
}

const ARIA_LABELS: Record<TrendDirection, string> = {
  stable: 'Rank stable — no significant movement',
  up: 'Rank rising — channel improving',
  down: 'Rank falling — channel declining',
};

export const RankShiftIndicator: React.FC<RankShiftIndicatorProps> = ({
  trend,
  size = 24,
  className,
}) => {
  const label = ARIA_LABELS[trend];

  if (trend === 'stable') {
    return (
      <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className={className}
        aria-label={label}
        role="img"
      >
        <style>
          {`
            @keyframes rsi-breathe {
              0%, 100% { opacity: 0.6; }
              50% { opacity: 1; }
            }
            @media (prefers-reduced-motion: reduce) {
              .rsi-breathe { animation: none !important; opacity: 0.8; }
            }
          `}
        </style>
        <line
          x1="4"
          y1="12"
          x2="20"
          y2="12"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          className="text-emerald-500"
        />
        <circle
          cx="12"
          cy="12"
          r="2.5"
          fill="currentColor"
          className="text-emerald-500 rsi-breathe"
          style={{ animation: 'rsi-breathe 4s ease-in-out infinite' }}
        />
      </svg>
    );
  }

  if (trend === 'up') {
    return (
      <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className={className}
        aria-label={label}
        role="img"
      >
        <style>
          {`
            @keyframes rsi-rise {
              0%, 100% { transform: translateY(0); }
              50% { transform: translateY(-2px); }
            }
            @media (prefers-reduced-motion: reduce) {
              .rsi-rise { animation: none !important; }
            }
          `}
        </style>
        <g
          className="rsi-rise"
          style={{ animation: 'rsi-rise 2.8s ease-in-out infinite' }}
        >
          <path
            d="M12 19V5"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            className="text-emerald-500"
          />
          <path
            d="M5 12l7-7 7 7"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="text-emerald-500"
          />
        </g>
      </svg>
    );
  }

  // trend === 'down'
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-label={label}
      role="img"
    >
      <style>
        {`
          @keyframes rsi-fall {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(2px); }
          }
          @media (prefers-reduced-motion: reduce) {
            .rsi-fall { animation: none !important; }
          }
        `}
      </style>
      <g
        className="rsi-fall"
        style={{ animation: 'rsi-fall 2.8s ease-in-out infinite' }}
      >
        <path
          d="M12 5v14"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          className="text-red-500"
        />
        <path
          d="M19 12l-7 7-7-7"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="text-red-500"
        />
      </g>
    </svg>
  );
};
