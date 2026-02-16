/**
 * A3-PRISM Signature Animation: ConvergenceGapBars
 *
 * Two horizontal bars (Platform-reported vs Skeldir-verified) that converge.
 * Gap width = (1 - confidence/100) * maxGap.
 * High confidence: overlap. Low: visible gap with pulsing glow.
 */

import { useEffect, useRef, useState } from 'react';

interface ConvergenceGapBarsProps {
  confidence: number;
  /** Reserved for future pulse-on-update behavior */
  isUpdating?: boolean;
  width?: number;
  height?: number;
  className?: string;
}

const ANIM_DURATION = 800;
const BREATHE_DURATION = 3000;

export function ConvergenceGapBars({
  confidence,
  isUpdating: _isUpdating = false,
  width = 200,
  height = 32,
  className,
}: ConvergenceGapBarsProps) {
  const [mounted, setMounted] = useState(false);
  const [pulsePhase, setPulsePhase] = useState(0);
  const animRef = useRef<number>();
  const reducedMotion = useRef(false);

  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    reducedMotion.current = mq.matches;
    const h = (e: MediaQueryListEvent) => { reducedMotion.current = e.matches; };
    mq.addEventListener('change', h);
    return () => mq.removeEventListener('change', h);
  }, []);

  useEffect(() => {
    const t = setTimeout(() => setMounted(true), 50);
    return () => clearTimeout(t);
  }, []);

  // Breathe for low confidence gap
  useEffect(() => {
    if (confidence > 50 || reducedMotion.current) return;
    let start = 0;
    const animate = (time: number) => {
      if (!start) start = time;
      const phase = ((time - start) % BREATHE_DURATION) / BREATHE_DURATION;
      setPulsePhase((Math.sin(phase * 2 * Math.PI) + 1) / 2);
      animRef.current = requestAnimationFrame(animate);
    };
    animRef.current = requestAnimationFrame(animate);
    return () => { if (animRef.current) cancelAnimationFrame(animRef.current); };
  }, [confidence]);

  const maxGap = width * 0.4;
  const gap = (1 - confidence / 100) * maxGap;
  const barHeight = height * 0.28;
  const cy = height / 2;
  const barWidth = (width - gap) / 2;

  // Animated positions
  const leftEnd = mounted ? barWidth : 0;
  const rightStart = mounted ? width - barWidth : width;

  const isLow = confidence <= 50;
  const isMed = confidence > 50 && confidence <= 80;
  const gapOpacity = isLow ? 0.15 + pulsePhase * 0.25 : isMed ? 0.1 : 0;

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={className}
      role="img"
      aria-label={`Verification convergence: ${confidence}% — ${gap < 2 ? 'aligned' : 'gap detected'}`}
    >
      {/* Gap glow */}
      {gap > 1 && (
        <rect
          x={leftEnd}
          y={cy - barHeight}
          width={Math.max(0, rightStart - leftEnd)}
          height={barHeight * 2}
          fill={isLow ? 'var(--brand-error, currentColor)' : 'var(--brand-warning, currentColor)'}
          opacity={gapOpacity}
          rx={2}
        />
      )}

      {/* Platform bar (left) */}
      <rect
        x={0}
        y={cy - barHeight / 2}
        width={leftEnd}
        height={barHeight}
        fill="var(--brand-tufts, currentColor)"
        opacity={0.7}
        rx={2}
        style={{
          transition: reducedMotion.current ? 'none' : `width ${ANIM_DURATION}ms cubic-bezier(0.4, 0, 0.2, 1)`,
        }}
      />

      {/* Verified bar (right) */}
      <rect
        x={rightStart}
        y={cy - barHeight / 2}
        width={width - rightStart}
        height={barHeight}
        fill="var(--brand-tufts, currentColor)"
        opacity={0.9}
        rx={2}
        style={{
          transition: reducedMotion.current ? 'none' : `x ${ANIM_DURATION}ms cubic-bezier(0.4, 0, 0.2, 1), width ${ANIM_DURATION}ms cubic-bezier(0.4, 0, 0.2, 1)`,
        }}
      />

      {/* Labels */}
      <text x={4} y={height - 3} className="fill-current" opacity={0.4} fontSize={9} fontFamily="var(--font-mono, monospace)">Platform</text>
      <text x={width - 4} y={height - 3} className="fill-current" opacity={0.4} fontSize={9} fontFamily="var(--font-mono, monospace)" textAnchor="end">Verified</text>

      <style>{`
        @media (prefers-reduced-motion: reduce) {
          rect { transition: none !important; }
        }
      `}</style>
    </svg>
  );
}
