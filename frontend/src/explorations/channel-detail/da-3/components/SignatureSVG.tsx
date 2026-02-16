/**
 * DA-3 TIMELINE — Signature SVG: Attribution Flow River
 *
 * Animated particle flow visualization:
 * - Source node (left, channel name) --> Destination node (right, "Verified Revenue")
 * - Small circles (3-4px) flowing left-to-right along curved bezier paths
 * - 8-12 particles in continuous loop with staggered start times
 * - Particle color = channel color from CHANNEL_COLORS
 * - Subtle glow on particles (SVG filter)
 * - prefers-reduced-motion: show static particles at fixed positions
 *
 * No client-side calculations. Pure visual signature element.
 */

import React from 'react';

/* -- Design Tokens -------------------------------------------------------- */
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
  border: {
    subtle: 'rgba(139,154,184,0.12)',
  },
  font: {
    heading: "'Syne', sans-serif",
    body: "'IBM Plex Sans', sans-serif",
    mono: "'IBM Plex Mono', monospace",
  },
  motion: {
    short: '200ms',
  },
} as const;

/* -- Bezier path definitions for variety --------------------------------- */
const FLOW_PATHS = [
  'M 80,60 C 220,20 380,100 520,60',
  'M 80,75 C 200,45 400,105 520,75',
  'M 80,90 C 240,60 360,120 520,90',
  'M 80,75 C 180,110 420,40 520,75',
];

/* -- Particle definitions (10 particles, staggered) ---------------------- */
interface ParticleDef {
  pathIndex: number;
  delay: number;      // animation-delay in seconds
  duration: number;   // animation-duration in seconds
  size: number;       // radius in px
  opacity: number;    // base opacity
  staticOffset: number; // 0-1, position along path for reduced-motion
}

const PARTICLES: ParticleDef[] = [
  { pathIndex: 0, delay: 0,    duration: 3.2, size: 3,   opacity: 0.9, staticOffset: 0.1 },
  { pathIndex: 1, delay: 0.4,  duration: 3.5, size: 3.5, opacity: 1.0, staticOffset: 0.25 },
  { pathIndex: 2, delay: 0.8,  duration: 3.0, size: 3,   opacity: 0.8, staticOffset: 0.4 },
  { pathIndex: 3, delay: 1.2,  duration: 3.8, size: 4,   opacity: 0.9, staticOffset: 0.55 },
  { pathIndex: 0, delay: 1.6,  duration: 3.4, size: 3,   opacity: 0.7, staticOffset: 0.7 },
  { pathIndex: 1, delay: 2.0,  duration: 3.1, size: 3.5, opacity: 0.85, staticOffset: 0.85 },
  { pathIndex: 2, delay: 2.4,  duration: 3.6, size: 3,   opacity: 0.9, staticOffset: 0.15 },
  { pathIndex: 3, delay: 2.8,  duration: 3.3, size: 4,   opacity: 0.75, staticOffset: 0.35 },
  { pathIndex: 0, delay: 3.2,  duration: 3.7, size: 3.5, opacity: 0.8, staticOffset: 0.6 },
  { pathIndex: 1, delay: 3.6,  duration: 3.0, size: 3,   opacity: 0.9, staticOffset: 0.8 },
];

/* -- CSS for reduced-motion ----------------------------------------------- */
const reducedMotionCSS = `
@media (prefers-reduced-motion: reduce) {
  .da3-flow-particle {
    animation: none !important;
  }
  .da3-flow-particle-static {
    display: block !important;
  }
  .da3-flow-particle-animated {
    display: none !important;
  }
}
@media (prefers-reduced-motion: no-preference) {
  .da3-flow-particle-static {
    display: none !important;
  }
  .da3-flow-particle-animated {
    display: block !important;
  }
}
`;

/* -- Component ------------------------------------------------------------ */

interface SignatureSVGProps {
  channelName: string;
  channelColor: string;
  verifiedRevenueFormatted: string;
}

export const SignatureSVG: React.FC<SignatureSVGProps> = ({
  channelName,
  channelColor,
  verifiedRevenueFormatted,
}) => {
  const svgWidth = 600;
  const svgHeight = 150;

  return (
    <section
      role="img"
      aria-label={`Attribution flow: ${channelName} revenue flowing to verified total`}
      style={{
        background: tokens.bg.card,
        borderRadius: '8px',
        border: `1px solid ${tokens.border.subtle}`,
        padding: '20px 24px',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
      }}
    >
      <style>{reducedMotionCSS}</style>

      {/* Title */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span
          style={{
            fontFamily: tokens.font.heading,
            fontSize: '13px',
            fontWeight: 500,
            color: tokens.text.muted,
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
          }}
        >
          Attribution Flow
        </span>
      </div>

      {/* SVG visualization */}
      <div style={{ width: '100%', overflow: 'hidden' }}>
        <svg
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          width="100%"
          height="auto"
          style={{ display: 'block', maxHeight: '150px' }}
        >
          <defs>
            {/* Particle glow filter */}
            <filter id="da3-particle-glow" x="-100%" y="-100%" width="300%" height="300%">
              <feGaussianBlur in="SourceGraphic" stdDeviation="2" result="blur" />
              <feColorMatrix
                in="blur"
                type="matrix"
                values={`1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 0.6 0`}
                result="glow"
              />
              <feMerge>
                <feMergeNode in="glow" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>

            {/* Path definitions */}
            {FLOW_PATHS.map((d, i) => (
              <path key={`path-def-${i}`} id={`da3-flow-path-${i}`} d={d} fill="none" />
            ))}
          </defs>

          {/* Visible guide paths (very subtle) */}
          {FLOW_PATHS.map((d, i) => (
            <path
              key={`guide-${i}`}
              d={d}
              fill="none"
              stroke={channelColor}
              strokeWidth="0.5"
              strokeOpacity={0.08}
            />
          ))}

          {/* Source node (left) */}
          <g>
            <rect
              x="8"
              y="55"
              width="60"
              height="40"
              rx="6"
              fill={tokens.bg.nested}
              stroke={channelColor}
              strokeWidth="1"
              strokeOpacity={0.3}
            />
            <circle cx="24" cy="75" r="4" fill={channelColor} opacity={0.8} />
            <text
              x="34"
              y="80"
              fontFamily={tokens.font.body}
              fontSize="8"
              fill={tokens.text.secondary}
              textAnchor="start"
            >
              {channelName.length > 6 ? channelName.slice(0, 6) : channelName}
            </text>
          </g>

          {/* Destination node (right) */}
          <g>
            <rect
              x="530"
              y="48"
              width="62"
              height="54"
              rx="6"
              fill={tokens.bg.nested}
              stroke={tokens.text.muted}
              strokeWidth="1"
              strokeOpacity={0.3}
            />
            <text
              x="561"
              y="70"
              fontFamily={tokens.font.body}
              fontSize="7"
              fill={tokens.text.muted}
              textAnchor="middle"
            >
              Verified
            </text>
            <text
              x="561"
              y="80"
              fontFamily={tokens.font.body}
              fontSize="7"
              fill={tokens.text.muted}
              textAnchor="middle"
            >
              Revenue
            </text>
            <text
              x="561"
              y="94"
              fontFamily={tokens.font.mono}
              fontSize="8"
              fontWeight="600"
              fill={tokens.text.primary}
              textAnchor="middle"
            >
              {verifiedRevenueFormatted}
            </text>
          </g>

          {/* Animated particles */}
          {PARTICLES.map((particle, i) => (
            <g key={`particle-${i}`}>
              {/* Animated version (hidden if reduced-motion) */}
              <circle
                className="da3-flow-particle da3-flow-particle-animated"
                r={particle.size}
                fill={channelColor}
                opacity={particle.opacity}
                filter="url(#da3-particle-glow)"
              >
                <animateMotion
                  dur={`${particle.duration}s`}
                  repeatCount="indefinite"
                  begin={`${particle.delay}s`}
                >
                  <mpath href={`#da3-flow-path-${particle.pathIndex}`} />
                </animateMotion>
              </circle>

              {/* Static version (shown if reduced-motion) */}
              <circle
                className="da3-flow-particle-static"
                r={particle.size}
                fill={channelColor}
                opacity={particle.opacity * 0.6}
                style={{ display: 'none' }}
              >
                <animateMotion
                  dur="0.001s"
                  repeatCount="1"
                  fill="freeze"
                  keyPoints={`${particle.staticOffset};${particle.staticOffset}`}
                  keyTimes="0;1"
                >
                  <mpath href={`#da3-flow-path-${particle.pathIndex}`} />
                </animateMotion>
              </circle>
            </g>
          ))}
        </svg>
      </div>
    </section>
  );
};

export default SignatureSVG;
