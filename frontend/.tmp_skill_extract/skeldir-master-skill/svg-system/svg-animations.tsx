/**
 * SKELDIR SVG ANIMATION SYSTEM
 *
 * Each component here is a functional motion primitive.
 * Every animation encodes a Bayesian or statistical concept.
 * No animation exists for decoration alone.
 *
 * Usage guide in SKILL.md Part 3.
 */

import React, { useEffect, useRef, useState } from 'react';
import { getConfidenceTokens, ConfidenceLevel, motion as motionTokens } from '../tokens/design-tokens';

// ─────────────────────────────────────────────────────────────────
// SVG-01: ConfidenceBreath
// Encodes: Posterior distribution width = uncertainty.
// Narrow breathing = high confidence. Wide oscillation = low confidence.
// ─────────────────────────────────────────────────────────────────

export interface ConfidenceBreathProps {
  confidence: ConfidenceLevel;
  pointEstimate: number;   // 0–1 normalized (0 = domain min, 1 = domain max)
  lowerBound: number;      // 0–1 normalized
  upperBound: number;      // 0–1 normalized
  isLive?: boolean;        // When true, breathing animation runs
  hasNewData?: boolean;    // Toggle to trigger pulse animation on update
  width?: number;
  height?: number;
  formatLower?: string;    // Pre-formatted lower bound label e.g. "$2.80"
  formatPoint?: string;    // Pre-formatted point estimate label e.g. "$3.20"
  formatUpper?: string;    // Pre-formatted upper bound label e.g. "$3.80"
  'aria-label'?: string;
}

export const ConfidenceBreath: React.FC<ConfidenceBreathProps> = ({
  confidence,
  pointEstimate,
  lowerBound,
  upperBound,
  isLive = true,
  hasNewData = false,
  width = 280,
  height = 64,
  formatLower,
  formatPoint,
  formatUpper,
  'aria-label': ariaLabel,
}) => {
  const tokens = getConfidenceTokens(confidence);
  const pulseRef = useRef<SVGCircleElement>(null);

  // Normalize positions to SVG coordinates
  const padX = 24;
  const trackWidth = width - padX * 2;
  const trackY = height / 2;

  const pxPoint = padX + pointEstimate * trackWidth;
  const pxLower = padX + lowerBound * trackWidth;
  const pxUpper = padX + upperBound * trackWidth;
  const rangeWidth = pxUpper - pxLower;

  const gradientId = `ci-grad-${confidence}`;
  const filterId = `ci-glow-${confidence}`;
  const pulseId = `ci-pulse-${confidence}`;

  // Trigger pulse on data update
  useEffect(() => {
    if (!hasNewData || !pulseRef.current) return;
    pulseRef.current.style.animation = 'none';
    void pulseRef.current.offsetWidth; // Reflow
    pulseRef.current.style.animation = `ci-pulse-ring ${motionTokens.pulse.duration} ${motionTokens.pulse.easing} forwards`;
  }, [hasNewData]);

  const breatheKeyframes = isLive ? `
    @keyframes ci-breathe-${confidence} {
      from { transform: scaleX(1); opacity: 0.55; }
      to   { transform: scaleX(${tokens.breatheScale}); opacity: 0.90; }
    }
    @keyframes ci-pulse-ring {
      0%   { r: 5; opacity: 0.8; }
      100% { r: 18; opacity: 0; }
    }
  ` : '';

  const rangeStyle: React.CSSProperties = isLive ? {
    animation: `ci-breathe-${confidence} ${tokens.breatheDuration} cubic-bezier(0.45,0,0.55,1) infinite alternate`,
    transformOrigin: `${pxPoint}px ${trackY}px`,
  } : {};

  return (
    <>
      {isLive && <style>{breatheKeyframes}</style>}
      <svg
        viewBox={`0 0 ${width} ${height}`}
        width={width}
        height={height}
        xmlns="http://www.w3.org/2000/svg"
        aria-label={ariaLabel ?? `Confidence interval: ${formatLower} to ${formatUpper}, estimate ${formatPoint}`}
        role="img"
      >
        <defs>
          <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%"   stopColor={tokens.color} stopOpacity={0}    />
            <stop offset="30%"  stopColor={tokens.color} stopOpacity={0.18} />
            <stop offset="50%"  stopColor={tokens.color} stopOpacity={0.38} />
            <stop offset="70%"  stopColor={tokens.color} stopOpacity={0.18} />
            <stop offset="100%" stopColor={tokens.color} stopOpacity={0}    />
          </linearGradient>
          <filter id={filterId} x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="2.5" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>

        {/* Track baseline */}
        <rect
          x={padX} y={trackY - 1}
          width={trackWidth} height={2}
          rx={1}
          fill="rgba(139,154,184,0.16)"
        />

        {/* Confidence range fill — the breathing element */}
        <rect
          x={pxLower} y={trackY - 9}
          width={rangeWidth} height={18}
          rx={9}
          fill={`url(#${gradientId})`}
          style={rangeStyle}
        />

        {/* Bound markers */}
        {[pxLower, pxUpper].map((x, i) => (
          <line
            key={i}
            x1={x} y1={trackY - 10}
            x2={x} y2={trackY + 10}
            stroke={tokens.color}
            strokeWidth={1.5}
            strokeOpacity={0.4}
          />
        ))}

        {/* Bound labels */}
        {formatLower && (
          <text x={pxLower} y={height - 4} textAnchor="middle" fontSize={9} fill={tokens.color} fillOpacity={0.7} fontFamily="'IBM Plex Mono', monospace">
            {formatLower}
          </text>
        )}
        {formatUpper && (
          <text x={pxUpper} y={height - 4} textAnchor="middle" fontSize={9} fill={tokens.color} fillOpacity={0.7} fontFamily="'IBM Plex Mono', monospace">
            {formatUpper}
          </text>
        )}
        {formatPoint && (
          <text x={pxPoint} y={height - 4} textAnchor="middle" fontSize={9} fill={tokens.color} fillOpacity={0.95} fontFamily="'IBM Plex Mono', monospace" fontWeight={600}>
            {formatPoint}
          </text>
        )}

        {/* Point estimate — outer glow */}
        <circle
          cx={pxPoint} cy={trackY}
          r={7}
          fill={tokens.color}
          opacity={0.25}
          filter={`url(#${filterId})`}
        />
        {/* Point estimate — filled dot */}
        <circle cx={pxPoint} cy={trackY} r={4.5} fill={tokens.color} />
        <circle cx={pxPoint} cy={trackY} r={2}   fill="white" />

        {/* Pulse ring — fires on data update */}
        <circle
          ref={pulseRef}
          cx={pxPoint} cy={trackY}
          r={5}
          fill="none"
          stroke={tokens.color}
          strokeWidth={1.5}
          style={{ opacity: 0 }}
        />
      </svg>
    </>
  );
};

// ─────────────────────────────────────────────────────────────────
// SVG-02: ModelBuildingProgress
// Encodes: 14-day evidence accumulation for Bayesian model initialization.
// Replaces spinner with semantically meaningful progress.
// ─────────────────────────────────────────────────────────────────

export interface ModelBuildingProgressProps {
  currentDay: number;   // 1–14
  totalDays?: number;   // Default 14
  connectedChannels: Array<{
    id: string;
    color: string;      // From channel color map
    name: string;
    daysOfData: number;
  }>;
  size?: number;        // SVG diameter
}

export const ModelBuildingProgress: React.FC<ModelBuildingProgressProps> = ({
  currentDay,
  totalDays = 14,
  connectedChannels,
  size = 180,
}) => {
  const cx = size / 2;
  const cy = size / 2;
  const r = size * 0.38;
  const strokeWidth = size * 0.055;

  // Compute arc path for a segment
  const segmentArc = (segIndex: number, total: number, filled: boolean, color: string) => {
    const gapDeg = 4; // degrees gap between segments
    const segDeg = 360 / total - gapDeg;
    const startAngle = (segIndex * (360 / total) - 90) * (Math.PI / 180);
    const endAngle   = (segIndex * (360 / total) - 90 + segDeg) * (Math.PI / 180);

    const x1 = cx + r * Math.cos(startAngle);
    const y1 = cy + r * Math.sin(startAngle);
    const x2 = cx + r * Math.cos(endAngle);
    const y2 = cy + r * Math.sin(endAngle);

    const largeArc = segDeg > 180 ? 1 : 0;

    return (
      <path
        key={segIndex}
        d={`M ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2}`}
        fill="none"
        stroke={filled ? color : 'rgba(139,154,184,0.15)'}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        style={filled ? {
          filter: `drop-shadow(0 0 4px ${color}60)`,
          animation: `segment-glow 2s ease-in-out infinite alternate`,
        } : undefined}
      />
    );
  };

  // Distribute channel colors across filled days
  const getSegmentColor = (dayIndex: number) => {
    // Weight colors by channel data availability
    if (connectedChannels.length === 0) return '#3D7BF5';
    const channelIdx = dayIndex % connectedChannels.length;
    return connectedChannels[channelIdx]?.color ?? '#3D7BF5';
  };

  return (
    <>
      <style>{`
        @keyframes segment-glow {
          from { opacity: 0.75; }
          to   { opacity: 1.0; }
        }
      `}</style>
      <svg
        viewBox={`0 0 ${size} ${size}`}
        width={size}
        height={size}
        aria-label={`Building model: day ${currentDay} of ${totalDays}. Accumulating evidence from ${connectedChannels.length} channels.`}
        role="progressbar"
        aria-valuenow={currentDay}
        aria-valuemin={1}
        aria-valuemax={totalDays}
      >
        {/* Segments */}
        {Array.from({ length: totalDays }, (_, i) => {
          const filled = i < currentDay;
          const color = filled ? getSegmentColor(i) : 'transparent';
          return segmentArc(i, totalDays, filled, color);
        })}

        {/* Center text */}
        <text
          x={cx} y={cy - 8}
          textAnchor="middle"
          fontSize={size * 0.18}
          fontWeight={700}
          fontFamily="'IBM Plex Mono', monospace"
          fill="#F0F4FF"
        >
          {currentDay}
        </text>
        <text
          x={cx} y={cy + size * 0.12}
          textAnchor="middle"
          fontSize={size * 0.075}
          fontFamily="'IBM Plex Sans', sans-serif"
          fill="#8B9AB8"
        >
          of {totalDays} days
        </text>
        <text
          x={cx} y={cy + size * 0.22}
          textAnchor="middle"
          fontSize={size * 0.062}
          fontFamily="'IBM Plex Sans', sans-serif"
          fill="#4A5568"
        >
          accumulating
        </text>
      </svg>
    </>
  );
};

// ─────────────────────────────────────────────────────────────────
// SVG-03: DiscrepancyGap
// Encodes: Delta between platform-claimed and verified revenue.
// Two converging bars; gap width = discrepancy magnitude.
// ─────────────────────────────────────────────────────────────────

export interface DiscrepancyGapProps {
  platformClaimed: number;   // Raw number (not formatted)
  verifiedRevenue: number;   // Raw number
  platformName: string;      // "Facebook", "Google"
  revenuSourceName: string;  // "Stripe", "Shopify"
  width?: number;
  height?: number;
}

export const DiscrepancyGap: React.FC<DiscrepancyGapProps> = ({
  platformClaimed,
  verifiedRevenue,
  platformName,
  revenuSourceName,
  width = 280,
  height = 80,
}) => {
  const percent = ((platformClaimed - verifiedRevenue) / platformClaimed) * 100;
  const abs = Math.abs(percent);

  const severity = abs < 5 ? 'safe' : abs < 15 ? 'warning' : 'critical';
  const gapColor = {
    safe:     '#10D98C',
    warning:  '#F5A623',
    critical: '#F04E4E',
  }[severity];

  const padX = 8;
  const barH = 18;
  const trackW = width - padX * 2;
  const claimedY = height * 0.22;
  const verifiedY = height * 0.58;

  // Normalize bar widths relative to claimed (max)
  const maxVal = Math.max(platformClaimed, verifiedRevenue);
  const claimedW = (platformClaimed / maxVal) * trackW;
  const verifiedW = (verifiedRevenue  / maxVal) * trackW;

  const pulseAnimation = severity === 'critical' ? `
    @keyframes gap-pulse {
      0%, 100% { opacity: 0.6; }
      50%       { opacity: 1.0; }
    }
  ` : '';

  return (
    <>
      {severity === 'critical' && <style>{pulseAnimation}</style>}
      <svg
        viewBox={`0 0 ${width} ${height}`}
        width={width}
        height={height}
        aria-label={`${platformName} claims ${percent > 0 ? '+' : ''}${Math.abs(percent).toFixed(1)}% more revenue than verified by ${revenuSourceName}`}
        role="img"
      >
        {/* Platform claimed bar */}
        <rect
          x={padX} y={claimedY}
          width={claimedW} height={barH}
          rx={4}
          fill="rgba(61,123,245,0.25)"
          stroke="rgba(61,123,245,0.5)"
          strokeWidth={1}
        />
        <text x={padX + 6} y={claimedY + barH / 2 + 4} fontSize={9} fill="#8B9AB8" fontFamily="'IBM Plex Sans', sans-serif">
          {platformName} claimed
        </text>

        {/* Verified bar */}
        <rect
          x={padX} y={verifiedY}
          width={verifiedW} height={barH}
          rx={4}
          fill="rgba(16,217,140,0.20)"
          stroke="rgba(16,217,140,0.45)"
          strokeWidth={1}
        />
        <text x={padX + 6} y={verifiedY + barH / 2 + 4} fontSize={9} fill="#8B9AB8" fontFamily="'IBM Plex Sans', sans-serif">
          {revenuSourceName} verified
        </text>

        {/* Gap indicator */}
        {abs >= 2 && (
          <>
            <line
              x1={padX + verifiedW} y1={verifiedY - 4}
              x2={padX + claimedW}  y2={claimedY + barH + 4}
              stroke={gapColor}
              strokeWidth={1}
              strokeDasharray="2 2"
              strokeOpacity={0.6}
              style={severity === 'critical' ? { animation: 'gap-pulse 1.5s ease-in-out infinite' } : undefined}
            />
            <text
              x={(padX + verifiedW + padX + claimedW) / 2 + 6}
              y={(verifiedY + claimedY + barH) / 2 + 3}
              fontSize={10}
              fontWeight={600}
              fill={gapColor}
              fontFamily="'IBM Plex Mono', monospace"
            >
              -{abs.toFixed(1)}%
            </text>
          </>
        )}
      </svg>
    </>
  );
};
