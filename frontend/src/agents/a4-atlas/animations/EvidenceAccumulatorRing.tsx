/**
 * A4-ATLAS Signature Animation: EvidenceAccumulatorRing
 *
 * 14-segment circular SVG. Each segment = 1 day of Bayesian model window.
 * Filled segments glow with brand primary. Ring breathes (1.0→1.02, 3000ms).
 * On update, newest segment pulses over 500ms.
 */

import { useEffect, useRef, useState } from 'react';

interface EvidenceAccumulatorRingProps {
  daysOfEvidence: number;
  confidence: number;
  isUpdating?: boolean;
  size?: number;
  className?: string;
}

const SEGMENTS = 14;
const BREATHE_MS = 3000;
const PULSE_MS = 500;
const GAP_DEG = 3;
const SEG_DEG = (360 - SEGMENTS * GAP_DEG) / SEGMENTS;

function polarToCart(cx: number, cy: number, r: number, deg: number) {
  const rad = ((deg - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function arcPath(cx: number, cy: number, r: number, startDeg: number, endDeg: number) {
  const s = polarToCart(cx, cy, r, startDeg);
  const e = polarToCart(cx, cy, r, endDeg);
  const large = endDeg - startDeg > 180 ? 1 : 0;
  return `M ${s.x} ${s.y} A ${r} ${r} 0 ${large} 1 ${e.x} ${e.y}`;
}

export function EvidenceAccumulatorRing({ daysOfEvidence, confidence, isUpdating = false, size = 120, className }: EvidenceAccumulatorRingProps) {
  const [scale, setScale] = useState(1);
  const [pulseIdx, setPulseIdx] = useState(-1);
  const animRef = useRef<number>();
  const reduced = useRef(false);

  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    reduced.current = mq.matches;
    const h = (e: MediaQueryListEvent) => { reduced.current = e.matches; };
    mq.addEventListener('change', h); return () => mq.removeEventListener('change', h);
  }, []);

  // Breathe
  useEffect(() => {
    if (reduced.current) return;
    let start = 0;
    const animate = (t: number) => {
      if (!start) start = t;
      const phase = ((t - start) % BREATHE_MS) / BREATHE_MS;
      setScale(1 + 0.02 * ((Math.sin(phase * 2 * Math.PI) + 1) / 2));
      animRef.current = requestAnimationFrame(animate);
    };
    animRef.current = requestAnimationFrame(animate);
    return () => { if (animRef.current) cancelAnimationFrame(animRef.current); };
  }, []);

  // Pulse newest segment on update
  useEffect(() => {
    if (isUpdating && daysOfEvidence > 0) {
      setPulseIdx(daysOfEvidence - 1);
      const t = setTimeout(() => setPulseIdx(-1), PULSE_MS);
      return () => clearTimeout(t);
    }
  }, [isUpdating, daysOfEvidence]);

  const cx = size / 2, cy = size / 2;
  const outerR = size * 0.42, innerR = size * 0.32;

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className={className}
      role="img" aria-label={`Model evidence: Day ${daysOfEvidence} of ${SEGMENTS}. ${confidence}% confidence`}>
      <g style={{ transform: `scale(${scale})`, transformOrigin: `${cx}px ${cy}px`, transition: reduced.current ? 'none' : undefined }}>
        {Array.from({ length: SEGMENTS }).map((_, i) => {
          const startDeg = i * (SEG_DEG + GAP_DEG);
          const endDeg = startDeg + SEG_DEG;
          const filled = i < daysOfEvidence;
          const isPulsing = i === pulseIdx;

          return (
            <path
              key={i}
              d={arcPath(cx, cy, outerR, startDeg, endDeg)}
              fill="none"
              stroke={filled ? 'var(--brand-tufts, currentColor)' : 'currentColor'}
              strokeWidth={outerR - innerR}
              strokeLinecap="round"
              opacity={filled ? (isPulsing ? 1 : 0.7) : 0.1}
              style={{
                filter: filled ? 'drop-shadow(0 0 3px var(--brand-tufts, currentColor))' : 'none',
                transition: reduced.current ? 'none' : `opacity ${PULSE_MS}ms ease`,
              }}
            />
          );
        })}

        {/* Center text */}
        <text x={cx} y={cy - 4} textAnchor="middle" className="fill-current" opacity={0.7}
          fontSize={12} fontFamily="var(--font-mono, monospace)" fontWeight={600}>
          Day {daysOfEvidence}
        </text>
        <text x={cx} y={cy + 10} textAnchor="middle" className="fill-current" opacity={0.4}
          fontSize={9} fontFamily="var(--font-mono, monospace)">
          of {SEGMENTS}
        </text>
      </g>
    </svg>
  );
}
