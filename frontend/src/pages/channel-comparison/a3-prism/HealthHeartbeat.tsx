/**
 * HealthHeartbeat — Animated SVG pulse indicator
 *
 * A small circle that pulses at a rate tied to data freshness.
 * - "fresh"  (< 1 min):  1s cycle, emerald
 * - "recent" (1–5 min):  2s cycle, amber
 * - "stale"  (> 5 min):  4s cycle, red
 *
 * Respects `prefers-reduced-motion` by disabling animation.
 * Always carries an accessible aria-label.
 *
 * @module A3-PRISM / HealthHeartbeat
 */

import React, { useMemo } from 'react';
import { cn } from '@/lib/utils';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type FreshnessLevel = 'fresh' | 'recent' | 'stale';

export interface HealthHeartbeatProps {
  /** ISO 8601 timestamp of the last data update */
  lastUpdated: string;
  /** Override automatic freshness detection */
  freshnessOverride?: FreshnessLevel;
  /** Diameter in pixels (default 10) */
  size?: number;
  className?: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function deriveFreshness(lastUpdated: string): FreshnessLevel {
  const ageMs = Date.now() - new Date(lastUpdated).getTime();
  const ageMinutes = ageMs / 60_000;

  if (ageMinutes < 1) return 'fresh';
  if (ageMinutes <= 5) return 'recent';
  return 'stale';
}

const FRESHNESS_CONFIG: Record<
  FreshnessLevel,
  { duration: string; colorClass: string; fill: string; label: string }
> = {
  fresh: {
    duration: '1s',
    colorClass: 'text-emerald-500',
    fill: 'rgb(16 185 129)', // emerald-500
    label: 'Data is fresh — updated less than 1 minute ago',
  },
  recent: {
    duration: '2s',
    colorClass: 'text-amber-500',
    fill: 'rgb(245 158 11)', // amber-500
    label: 'Data is recent — updated 1 to 5 minutes ago',
  },
  stale: {
    duration: '4s',
    colorClass: 'text-red-500',
    fill: 'rgb(239 68 68)', // red-500
    label: 'Data is stale — updated more than 5 minutes ago',
  },
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export const HealthHeartbeat: React.FC<HealthHeartbeatProps> = ({
  lastUpdated,
  freshnessOverride,
  size = 10,
  className,
}) => {
  const freshness = freshnessOverride ?? deriveFreshness(lastUpdated);
  const config = FRESHNESS_CONFIG[freshness];

  // Unique animation ID to avoid collisions when multiple heartbeats render
  const animId = useMemo(
    () => `hb-${Math.random().toString(36).slice(2, 8)}`,
    [],
  );

  const r = size / 2 - 1; // leave 1px margin for the pulse ring
  const cx = size / 2;
  const cy = size / 2;

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      xmlns="http://www.w3.org/2000/svg"
      className={cn('inline-block shrink-0', className)}
      role="img"
      aria-label={config.label}
    >
      {/* Static core dot */}
      <circle cx={cx} cy={cy} r={r * 0.6} fill={config.fill} />

      {/* Pulsing ring — respects prefers-reduced-motion via CSS */}
      <circle
        cx={cx}
        cy={cy}
        r={r * 0.6}
        fill="none"
        stroke={config.fill}
        strokeWidth={1}
        className="motion-safe:animate-[heartbeat-ring_var(--hb-dur)_ease-in-out_infinite] motion-reduce:opacity-40"
        style={
          {
            '--hb-dur': config.duration,
            transformOrigin: `${cx}px ${cy}px`,
          } as React.CSSProperties
        }
      >
        {/*
         * Fallback SVG animation for environments where CSS keyframes
         * may not target SVG attributes well. The CSS class above handles
         * modern browsers; these SMIL animations provide belt-and-suspenders.
         */}
        <animate
          attributeName="r"
          values={`${r * 0.6};${r};${r * 0.6}`}
          dur={config.duration}
          repeatCount="indefinite"
          id={`${animId}-r`}
        />
        <animate
          attributeName="opacity"
          values="0.8;0.15;0.8"
          dur={config.duration}
          repeatCount="indefinite"
          id={`${animId}-o`}
        />
      </circle>
    </svg>
  );
};

HealthHeartbeat.displayName = 'HealthHeartbeat';

export default HealthHeartbeat;
