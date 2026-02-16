/**
 * DA-4 ANALYST — Discrepancy Convergence SVG
 *
 * Two horizontal bars (platform claimed vs verified) with animated gap.
 * Gap pulses red if discrepancy > 15%, amber glow 5-15%, green static < 5%.
 */

import React from 'react';

const tokens = {
  text: { primary: '#F0F4FF', secondary: '#8B9AB8', muted: '#4A5568' },
  confidence: { high: '#10D98C', medium: '#F5A623', low: '#F04E4E' },
  brand: '#3D7BF5',
  border: { subtle: 'rgba(139,154,184,0.12)' },
};

interface SignatureSVGProps {
  platformClaimed: number;
  platformClaimedFormatted: string;
  verified: number;
  verifiedFormatted: string;
  discrepancyPercent: number;
  discrepancyFormatted: string;
  platformName: string;
  revenueSource: string;
}

const getSeverity = (pct: number): { color: string; pulse: boolean } => {
  const abs = Math.abs(pct);
  if (abs > 15) return { color: tokens.confidence.low, pulse: true };
  if (abs > 5) return { color: tokens.confidence.medium, pulse: false };
  return { color: tokens.confidence.high, pulse: false };
};

export const SignatureSVG: React.FC<SignatureSVGProps> = ({
  platformClaimed,
  platformClaimedFormatted,
  verified,
  verifiedFormatted,
  discrepancyPercent,
  discrepancyFormatted,
  platformName,
  revenueSource,
}) => {
  const max = Math.max(platformClaimed, verified);
  const claimedWidth = max > 0 ? (platformClaimed / max) * 240 : 0;
  const verifiedWidth = max > 0 ? (verified / max) * 240 : 0;
  const severity = getSeverity(discrepancyPercent);

  return (
    <>
      <style>{`
        @keyframes da4-gap-pulse {
          0%, 100% { opacity: 0.25; }
          50% { opacity: 0.6; }
        }
        @media (prefers-reduced-motion: reduce) {
          .da4-gap-pulse { animation: none !important; opacity: 0.35 !important; }
        }
      `}</style>
      <svg
        viewBox="0 0 320 120"
        width="100%"
        style={{ maxWidth: '320px', display: 'block' }}
        role="img"
        aria-label={`Revenue discrepancy: ${platformName} claims ${platformClaimedFormatted}, ${revenueSource} verified ${verifiedFormatted}. Discrepancy is ${discrepancyFormatted}.`}
      >
        {/* Platform claimed bar */}
        <text x="8" y="18" fill={tokens.text.secondary} fontSize="10" fontFamily="'IBM Plex Sans', sans-serif">
          {platformName} Claims
        </text>
        <rect x="8" y="24" width={claimedWidth} height="20" rx="4" fill="rgba(61,123,245,0.25)" stroke={tokens.brand} strokeWidth="1" />
        <text x={claimedWidth + 14} y="38" fill={tokens.text.primary} fontSize="12" fontFamily="'IBM Plex Mono', monospace" fontWeight="600">
          {platformClaimedFormatted}
        </text>

        {/* Gap area */}
        {severity.pulse && (
          <rect
            className="da4-gap-pulse"
            x="8"
            y="46"
            width={Math.max(claimedWidth, verifiedWidth)}
            height="24"
            rx="2"
            fill={severity.color}
            style={{
              opacity: 0.25,
              animation: 'da4-gap-pulse 1.5s ease-in-out infinite',
            }}
          />
        )}

        {/* Discrepancy label in gap */}
        <text
          x={Math.max(claimedWidth, verifiedWidth) / 2 + 8}
          y="62"
          fill={severity.color}
          fontSize="12"
          fontFamily="'IBM Plex Mono', monospace"
          fontWeight="700"
          textAnchor="middle"
        >
          {discrepancyFormatted}
        </text>

        {/* Dashed connector lines */}
        <line
          x1={claimedWidth + 8}
          y1="44"
          x2={claimedWidth + 8}
          y2="48"
          stroke={severity.color}
          strokeWidth="1"
          strokeDasharray="2,2"
        />
        <line
          x1={verifiedWidth + 8}
          y1="68"
          x2={verifiedWidth + 8}
          y2="72"
          stroke={severity.color}
          strokeWidth="1"
          strokeDasharray="2,2"
        />

        {/* Verified bar */}
        <text x="8" y="86" fill={tokens.text.secondary} fontSize="10" fontFamily="'IBM Plex Sans', sans-serif">
          {revenueSource} Verified
        </text>
        <rect x="8" y="92" width={verifiedWidth} height="20" rx="4" fill="rgba(16,217,140,0.20)" stroke={tokens.confidence.high} strokeWidth="1" />
        <text x={verifiedWidth + 14} y="106" fill={tokens.text.primary} fontSize="12" fontFamily="'IBM Plex Mono', monospace" fontWeight="600">
          {verifiedFormatted}
        </text>
      </svg>
    </>
  );
};

export default SignatureSVG;
