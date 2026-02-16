/**
 * DA-1 COCKPIT — Signature SVG: Channel Sync Heartbeat
 *
 * ECG/EKG-style pulse line showing data freshness.
 * Animated pulse moves left-to-right, speed maps to data freshness.
 * Confidence color for the line with glow trail (feGaussianBlur).
 *
 * Respects prefers-reduced-motion: shows static line.
 * ARIA label announces data freshness to screen readers.
 */

import React, { useEffect, useId } from 'react';
import type { ConfidenceLevel } from '../../shared/types';

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

function getConfidenceColor(level: ConfidenceLevel): string {
  return tokens.confidence[level];
}

/* ── Props ──────────────────────────────────────────────────────── */

interface SignatureSVGProps {
  confidenceLevel: ConfidenceLevel;
  lastUpdatedFormatted: string;
  channelColor?: string;
}

/* ── Component ──────────────────────────────────────────────────── */

export const SignatureSVG: React.FC<SignatureSVGProps> = ({
  confidenceLevel,
  lastUpdatedFormatted,
  channelColor,
}) => {
  const uniqueId = useId();
  const confColor = channelColor || getConfidenceColor(confidenceLevel);
  const keyframesId = `da1-heartbeat-${uniqueId.replace(/:/g, '')}`;

  useEffect(() => {
    if (typeof document === 'undefined') return;
    if (document.getElementById(keyframesId)) return;

    const style = document.createElement('style');
    style.id = keyframesId;
    style.textContent = `
      @keyframes da1HeartbeatSweep {
        0% { transform: translateX(-100%); }
        100% { transform: translateX(100%); }
      }
      @keyframes da1HeartbeatFade {
        0%, 100% { opacity: 0.4; }
        50% { opacity: 1; }
      }
      @media (prefers-reduced-motion: reduce) {
        .da1-heartbeat-group { animation: none !important; }
        .da1-heartbeat-glow { animation: none !important; opacity: 0.6 !important; }
      }
    `;
    document.head.appendChild(style);

    return () => {
      const existing = document.getElementById(keyframesId);
      if (existing) existing.remove();
    };
  }, [keyframesId]);

  // ECG-style heartbeat path data.
  // Repeating pattern across the full viewbox width (0-600):
  // flat -> small dip -> sharp spike up -> sharp spike down -> return -> flat
  const heartbeatPath = [
    'M0,50',        // start at middle
    'L60,50',       // flat baseline
    'L75,45',       // small pre-beat dip
    'L85,50',       // return
    'L95,15',       // sharp QRS spike up
    'L105,80',      // sharp QRS spike down
    'L115,42',      // overshoot return
    'L125,50',      // settle
    'L150,50',      // flat
    'L165,45',      // T-wave bump
    'L180,50',      // return
    'L240,50',      // flat baseline
    'L255,45',      // pre-beat
    'L265,50',      // return
    'L275,15',      // QRS spike up
    'L285,80',      // QRS spike down
    'L295,42',      // overshoot
    'L305,50',      // settle
    'L330,50',      // flat
    'L345,45',      // T-wave
    'L360,50',      // return
    'L420,50',      // flat baseline
    'L435,45',      // pre-beat
    'L445,50',      // return
    'L455,15',      // QRS spike up
    'L465,80',      // QRS spike down
    'L475,42',      // overshoot
    'L485,50',      // settle
    'L510,50',      // flat
    'L525,45',      // T-wave
    'L540,50',      // return
    'L600,50',      // end flat
  ].join(' ');

  // Sweep duration: faster = more fresh. High confidence = 3s, Medium = 5s, Low = 8s
  const sweepDuration = confidenceLevel === 'high' ? 3 : confidenceLevel === 'medium' ? 5 : 8;

  const filterId = `da1-glow-filter-${uniqueId.replace(/:/g, '')}`;
  const clipId = `da1-sweep-clip-${uniqueId.replace(/:/g, '')}`;

  return (
    <div
      style={{
        padding: '20px 24px',
        background: tokens.bg.card,
        borderRadius: '8px',
        border: `1px solid ${tokens.border.subtle}`,
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
      }}
    >
      <style>
        {'@import url("https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700&family=IBM+Plex+Sans:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600;700&display=swap");'}
      </style>

      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '8px',
        }}
      >
        <span
          style={{
            fontFamily: tokens.font.heading,
            fontSize: '14px',
            fontWeight: 600,
            color: tokens.text.primary,
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
          }}
        >
          Channel Sync Heartbeat
        </span>
        <span
          style={{
            fontFamily: tokens.font.mono,
            fontSize: '11px',
            color: tokens.text.muted,
          }}
        >
          Updated {lastUpdatedFormatted}
        </span>
      </div>

      {/* SVG Heartbeat */}
      <svg
        viewBox="0 0 600 100"
        style={{
          width: '100%',
          height: '80px',
          overflow: 'hidden',
        }}
        role="img"
        aria-label={`Channel data freshness: updated ${lastUpdatedFormatted}`}
      >
        <defs>
          {/* Glow filter */}
          <filter id={filterId} x="-20%" y="-40%" width="140%" height="180%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>

          {/* Sweep mask clip */}
          <clipPath id={clipId}>
            <rect
              className="da1-heartbeat-group"
              x="0"
              y="0"
              width="600"
              height="100"
              style={{
                animation: `da1HeartbeatSweep ${sweepDuration}s linear infinite`,
              }}
            />
          </clipPath>
        </defs>

        {/* Background grid lines */}
        {[20, 40, 60, 80].map((y) => (
          <line
            key={y}
            x1="0"
            y1={y}
            x2="600"
            y2={y}
            stroke={tokens.border.subtle}
            strokeWidth="0.5"
          />
        ))}

        {/* Static base line (dimmed) */}
        <path
          d={heartbeatPath}
          fill="none"
          stroke={`${confColor}30`}
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* Animated glow trail */}
        <path
          className="da1-heartbeat-glow"
          d={heartbeatPath}
          fill="none"
          stroke={confColor}
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          filter={`url(#${filterId})`}
          style={{
            animation: `da1HeartbeatFade ${sweepDuration}s ease-in-out infinite`,
          }}
        />

        {/* Bright foreground line */}
        <path
          d={heartbeatPath}
          fill="none"
          stroke={confColor}
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>

      {/* Status indicators */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '8px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <div
            style={{
              width: '6px',
              height: '6px',
              borderRadius: '50%',
              backgroundColor: confColor,
              boxShadow: `0 0 6px ${confColor}80`,
            }}
          />
          <span
            style={{
              fontFamily: tokens.font.body,
              fontSize: '11px',
              color: tokens.text.secondary,
            }}
          >
            {confidenceLevel === 'high'
              ? 'Strong signal — data flowing normally'
              : confidenceLevel === 'medium'
                ? 'Moderate signal — accumulating data'
                : 'Weak signal — limited data available'}
          </span>
        </div>

        <span
          style={{
            fontFamily: tokens.font.mono,
            fontSize: '11px',
            color: tokens.text.muted,
          }}
        >
          {confidenceLevel === 'high' ? '~3s refresh' : confidenceLevel === 'medium' ? '~5s refresh' : '~8s refresh'}
        </span>
      </div>
    </div>
  );
};

export default SignatureSVG;
