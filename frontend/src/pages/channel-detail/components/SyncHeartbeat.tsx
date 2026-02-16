/**
 * Final Single Channel Detail — Channel Sync Heartbeat
 *
 * Based on DA-1 COCKPIT SignatureSVG.
 * Adapted for light theme: dark stroke on light background.
 *
 * ECG/EKG pulse line showing data freshness.
 * Speed maps to confidence level (high=fast, low=slow).
 * Respects prefers-reduced-motion.
 */

import React, { useEffect, useId } from 'react';
import type { ConfidenceLevel } from '@/explorations/channel-detail/shared/types';
import { tokens } from '../tokens';

interface SyncHeartbeatProps {
  confidenceLevel: ConfidenceLevel;
  lastUpdatedFormatted: string;
  channelColor?: string;
}

export const SyncHeartbeat: React.FC<SyncHeartbeatProps> = ({
  confidenceLevel,
  lastUpdatedFormatted,
  channelColor,
}) => {
  const uniqueId = useId();
  const confColor = channelColor || tokens.confidence[confidenceLevel];
  const keyframesId = `final-heartbeat-${uniqueId.replace(/:/g, '')}`;

  useEffect(() => {
    if (typeof document === 'undefined') return;
    if (document.getElementById(keyframesId)) return;

    const style = document.createElement('style');
    style.id = keyframesId;
    style.textContent = `
      @keyframes finalHeartbeatFade {
        0%, 100% { opacity: 0.3; }
        50% { opacity: 1; }
      }
      @media (prefers-reduced-motion: reduce) {
        .final-heartbeat-glow { animation: none !important; opacity: 0.6 !important; }
      }
    `;
    document.head.appendChild(style);

    return () => {
      const existing = document.getElementById(keyframesId);
      if (existing) existing.remove();
    };
  }, [keyframesId]);

  // ECG heartbeat path — repeating pattern across 600px viewbox
  const heartbeatPath = [
    'M0,50', 'L60,50', 'L75,45', 'L85,50', 'L95,15', 'L105,80', 'L115,42', 'L125,50',
    'L150,50', 'L165,45', 'L180,50', 'L240,50', 'L255,45', 'L265,50', 'L275,15',
    'L285,80', 'L295,42', 'L305,50', 'L330,50', 'L345,45', 'L360,50', 'L420,50',
    'L435,45', 'L445,50', 'L455,15', 'L465,80', 'L475,42', 'L485,50', 'L510,50',
    'L525,45', 'L540,50', 'L600,50',
  ].join(' ');

  const sweepDuration = confidenceLevel === 'high' ? 3 : confidenceLevel === 'medium' ? 5 : 8;
  const filterId = `final-glow-${uniqueId.replace(/:/g, '')}`;

  return (
    <div
      style={{
        padding: '20px 24px',
        background: tokens.bg.card,
        borderRadius: tokens.radius.md,
        border: `1px solid ${tokens.border.default}`,
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
        boxShadow: tokens.shadow.sm,
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
        <span style={{ fontFamily: tokens.font.heading, fontSize: '14px', fontWeight: 600, color: tokens.text.primary, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          Channel Sync Heartbeat
        </span>
        <span style={{ fontFamily: tokens.font.mono, fontSize: '11px', color: tokens.text.muted }}>
          Updated {lastUpdatedFormatted}
        </span>
      </div>

      {/* SVG */}
      <svg
        viewBox="0 0 600 100"
        style={{ width: '100%', height: '80px', overflow: 'hidden' }}
        role="img"
        aria-label={`Channel data freshness: updated ${lastUpdatedFormatted}`}
      >
        <defs>
          <filter id={filterId} x="-20%" y="-40%" width="140%" height="180%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="2" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Light background grid */}
        {[20, 40, 60, 80].map((y) => (
          <line key={y} x1="0" y1={y} x2="600" y2={y} stroke="rgba(0,0,0,0.04)" strokeWidth="0.5" />
        ))}

        {/* Static base line (dimmed) */}
        <path d={heartbeatPath} fill="none" stroke={`${confColor}20`} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />

        {/* Animated glow trail */}
        <path
          className="final-heartbeat-glow"
          d={heartbeatPath}
          fill="none"
          stroke={confColor}
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          filter={`url(#${filterId})`}
          style={{ animation: `finalHeartbeatFade ${sweepDuration}s ease-in-out infinite` }}
        />

        {/* Foreground line */}
        <path d={heartbeatPath} fill="none" stroke={confColor} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>

      {/* Status */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <div style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: confColor }} />
          <span style={{ fontFamily: tokens.font.body, fontSize: '11px', color: tokens.text.secondary }}>
            {confidenceLevel === 'high' ? 'Strong signal — data flowing normally' : confidenceLevel === 'medium' ? 'Moderate signal — accumulating data' : 'Weak signal — limited data available'}
          </span>
        </div>
        <span style={{ fontFamily: tokens.font.mono, fontSize: '11px', color: tokens.text.muted }}>
          {confidenceLevel === 'high' ? '~3s refresh' : confidenceLevel === 'medium' ? '~5s refresh' : '~8s refresh'}
        </span>
      </div>
    </div>
  );
};

export default SyncHeartbeat;
