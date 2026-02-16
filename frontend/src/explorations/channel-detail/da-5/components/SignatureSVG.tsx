/**
 * DA-5 COMPACT — Verification Progress Ring
 *
 * Circular progress indicator showing % of revenue verified.
 * Ring color = confidence tier. Fill animates on mount.
 */

import React, { useEffect, useState } from 'react';
import type { ConfidenceLevel } from '../../shared/types';

const tokens = {
  text: { primary: '#F0F4FF', secondary: '#8B9AB8' },
  confidence: { high: '#10D98C', medium: '#F5A623', low: '#F04E4E' },
  border: { subtle: 'rgba(139,154,184,0.12)' },
};

interface SignatureSVGProps {
  verified: number;
  platformClaimed: number;
  confidenceLevel: ConfidenceLevel;
}

export const SignatureSVG: React.FC<SignatureSVGProps> = ({
  verified,
  platformClaimed,
  confidenceLevel,
}) => {
  const percentage = platformClaimed > 0 ? Math.round((verified / platformClaimed) * 100) : 0;
  const color = tokens.confidence[confidenceLevel];

  // Circle math
  const size = 120;
  const strokeWidth = 8;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const targetOffset = circumference - (percentage / 100) * circumference;

  const [offset, setOffset] = useState(circumference);

  useEffect(() => {
    // Check for reduced motion
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (mq.matches) {
      setOffset(targetOffset);
      return;
    }
    // Animate after mount
    const timer = requestAnimationFrame(() => setOffset(targetOffset));
    return () => cancelAnimationFrame(timer);
  }, [targetOffset, circumference]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        role="progressbar"
        aria-valuenow={percentage}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${percentage}% of revenue verified`}
      >
        {/* Background ring */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={tokens.border.subtle}
          strokeWidth={strokeWidth}
        />
        {/* Progress ring */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{
            transition: 'stroke-dashoffset 1000ms cubic-bezier(0.4, 0, 0.2, 1)',
            transform: 'rotate(-90deg)',
            transformOrigin: '50% 50%',
          }}
        />
        {/* Percentage text */}
        <text
          x="50%"
          y="48%"
          textAnchor="middle"
          dominantBaseline="middle"
          fill={tokens.text.primary}
          fontSize="24"
          fontFamily="'IBM Plex Mono', monospace"
          fontWeight="600"
        >
          {percentage}%
        </text>
        {/* Label */}
        <text
          x="50%"
          y="66%"
          textAnchor="middle"
          dominantBaseline="middle"
          fill={tokens.text.secondary}
          fontSize="10"
          fontFamily="'IBM Plex Sans', sans-serif"
        >
          verified
        </text>
      </svg>
    </div>
  );
};

export default SignatureSVG;
