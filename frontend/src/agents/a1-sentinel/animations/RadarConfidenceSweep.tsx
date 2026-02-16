/**
 * A1-SENTINEL Signature Animation: RadarConfidenceSweep
 *
 * A circular SVG with a rotating gradient arm whose sweep angle
 * corresponds to Bayesian confidence interval width.
 *
 * High confidence (>80): narrow ~72° sweep, 4000ms rotation
 * Medium (50–80): moderate ~180° sweep, 3000ms rotation
 * Low (<50): wide ~290° sweep, 2000ms rotation
 *
 * On data update: 600ms pulse from center outward.
 * prefers-reduced-motion: static arc, no rotation.
 *
 * Master Skill citations:
 *   - SVG-01 ConfidenceBreath (amplitude ↔ uncertainty)
 *   - Motion tokens: breathe 3000ms, pulse 600ms
 *   - Anti-pattern: no decorative-only animation
 */

import { useEffect, useRef, useState } from 'react';

interface RadarConfidenceSweepProps {
  /** Confidence score 0–100 */
  confidence: number;
  /** Triggers the 600ms pulse animation */
  isUpdating?: boolean;
  /** Override size in px (default 64) */
  size?: number;
  className?: string;
}

function getSweepConfig(confidence: number) {
  if (confidence > 80) return { angle: 72, duration: 4000 };
  if (confidence > 50) return { angle: 180, duration: 3000 };
  return { angle: 290, duration: 2000 };
}

function polarToCartesian(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function describeArc(cx: number, cy: number, r: number, startAngle: number, endAngle: number) {
  const start = polarToCartesian(cx, cy, r, endAngle);
  const end = polarToCartesian(cx, cy, r, startAngle);
  const largeArc = endAngle - startAngle > 180 ? 1 : 0;
  return `M ${cx} ${cy} L ${start.x} ${start.y} A ${r} ${r} 0 ${largeArc} 0 ${end.x} ${end.y} Z`;
}

export function RadarConfidenceSweep({
  confidence,
  isUpdating = false,
  size = 64,
  className,
}: RadarConfidenceSweepProps) {
  const [pulseActive, setPulseActive] = useState(false);
  const prevUpdating = useRef(false);
  const rotationRef = useRef<number>(0);
  const animFrameRef = useRef<number>();
  const svgRef = useRef<SVGSVGElement>(null);
  const lastTimeRef = useRef<number>(0);
  const reducedMotion = useRef(false);

  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    reducedMotion.current = mq.matches;
    const handler = (e: MediaQueryListEvent) => { reducedMotion.current = e.matches; };
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  // Pulse trigger on data update
  useEffect(() => {
    if (isUpdating && !prevUpdating.current) {
      setPulseActive(true);
      const t = setTimeout(() => setPulseActive(false), 600);
      return () => clearTimeout(t);
    }
    prevUpdating.current = isUpdating;
  }, [isUpdating]);

  // Continuous rotation via requestAnimationFrame
  useEffect(() => {
    const { duration } = getSweepConfig(confidence);

    const animate = (time: number) => {
      if (!lastTimeRef.current) lastTimeRef.current = time;
      const delta = time - lastTimeRef.current;
      lastTimeRef.current = time;

      if (!reducedMotion.current) {
        rotationRef.current = (rotationRef.current + (360 * delta) / duration) % 360;
      }

      const sweepGroup = svgRef.current?.querySelector('[data-sweep]') as SVGElement | null;
      if (sweepGroup) {
        sweepGroup.style.transform = `rotate(${rotationRef.current}deg)`;
      }

      animFrameRef.current = requestAnimationFrame(animate);
    };

    animFrameRef.current = requestAnimationFrame(animate);
    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
      lastTimeRef.current = 0;
    };
  }, [confidence]);

  const { angle } = getSweepConfig(confidence);
  const cx = size / 2;
  const cy = size / 2;
  const radius = size * 0.42;
  const arcPath = describeArc(cx, cy, radius, 0, angle);

  // Concentric reference rings
  const ringRadii = [radius * 0.33, radius * 0.66, radius];

  return (
    <svg
      ref={svgRef}
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      className={className}
      role="img"
      aria-label={`Confidence radar: ${confidence}% — ${confidence > 80 ? 'high' : confidence > 50 ? 'medium' : 'low'} confidence`}
    >
      {/* Grid rings */}
      {ringRadii.map((r, i) => (
        <circle
          key={i}
          cx={cx}
          cy={cy}
          r={r}
          fill="none"
          stroke="currentColor"
          strokeOpacity={0.08 + i * 0.04}
          strokeWidth={0.5}
        />
      ))}

      {/* Cross-hair lines */}
      <line x1={cx} y1={cy - radius} x2={cx} y2={cy + radius} stroke="currentColor" strokeOpacity={0.06} strokeWidth={0.5} />
      <line x1={cx - radius} y1={cy} x2={cx + radius} y2={cy} stroke="currentColor" strokeOpacity={0.06} strokeWidth={0.5} />

      {/* Rotating sweep arm */}
      <g data-sweep style={{ transformOrigin: `${cx}px ${cy}px` }}>
        <defs>
          <linearGradient id={`sentinel-sweep-grad-${size}`} x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="var(--brand-tufts, currentColor)" stopOpacity={0.35} />
            <stop offset="100%" stopColor="var(--brand-tufts, currentColor)" stopOpacity={0} />
          </linearGradient>
        </defs>
        <path
          d={arcPath}
          fill={`url(#sentinel-sweep-grad-${size})`}
          opacity={0.7}
        />
        {/* Leading edge line */}
        <line
          x1={cx}
          y1={cy}
          x2={polarToCartesian(cx, cy, radius, angle).x}
          y2={polarToCartesian(cx, cy, radius, angle).y}
          stroke="var(--brand-tufts, currentColor)"
          strokeOpacity={0.5}
          strokeWidth={1}
        />
      </g>

      {/* Center dot (point estimate) */}
      <circle
        cx={cx}
        cy={cy}
        r={2.5}
        fill="var(--brand-tufts, currentColor)"
        opacity={0.9}
      />

      {/* Pulse ring on data update */}
      {pulseActive && (
        <circle
          cx={cx}
          cy={cy}
          r={radius * 0.15}
          fill="none"
          stroke="var(--brand-tufts, currentColor)"
          strokeWidth={1.5}
          opacity={0.8}
          className="sentinel-pulse-ring"
        >
          <animate
            attributeName="r"
            from={String(radius * 0.15)}
            to={String(radius)}
            dur="600ms"
            fill="freeze"
          />
          <animate
            attributeName="opacity"
            from="0.8"
            to="0"
            dur="600ms"
            fill="freeze"
          />
        </circle>
      )}

      <style>{`
        @media (prefers-reduced-motion: reduce) {
          [data-sweep] { animation: none !important; transition: none !important; }
          .sentinel-pulse-ring animate { dur: 0.01s; }
        }
      `}</style>
    </svg>
  );
}
