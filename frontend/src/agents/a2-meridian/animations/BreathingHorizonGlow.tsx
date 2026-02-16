/**
 * A2-MERIDIAN Signature Animation: BreathingHorizonGlow
 *
 * A full-width SVG gradient bar positioned behind metric cards,
 * oscillating opacity between 0.05 and 0.15 over a 3000ms breathe cycle.
 * The breathing rhythm communicates "the platform is alive, data is flowing."
 *
 * Confidence maps to gradient intensity — higher confidence produces
 * a more visible glow horizon. On data update, a 600ms pulse briefly
 * elevates opacity to full before resuming the breathe cycle.
 *
 * prefers-reduced-motion: static at 0.1 opacity, no animation.
 *
 * Master Skill citations:
 *   - SVG-01 ConfidenceBreath (amplitude maps uncertainty)
 *   - Motion tokens: breathe=3000ms, pulse=600ms
 *   - Anti-pattern: no decorative-only animation (encodes data freshness)
 *   - Token compliance: var(--brand-tufts) only, zero hardcoded hex
 */

import { useEffect, useRef, useState, useCallback } from 'react';

interface BreathingHorizonGlowProps {
  /** Confidence score 0-100 — maps to gradient intensity */
  confidence: number;
  /** When true, triggers a 600ms pulse to full opacity */
  isUpdating?: boolean;
  /** Optional className for container sizing */
  className?: string;
}

/** Motion tokens (ms) */
const BREATHE_DURATION = 3000;
const PULSE_DURATION = 600;
const OPACITY_MIN = 0.05;
const OPACITY_MAX = 0.15;
const OPACITY_STATIC = 0.1;

export function BreathingHorizonGlow({
  confidence,
  isUpdating = false,
  className,
}: BreathingHorizonGlowProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const animFrameRef = useRef<number>();
  const startTimeRef = useRef<number>(0);
  const reducedMotionRef = useRef(false);
  const [pulseActive, setPulseActive] = useState(false);
  const prevUpdatingRef = useRef(false);

  // Detect prefers-reduced-motion
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    reducedMotionRef.current = mq.matches;
    const handler = (e: MediaQueryListEvent) => {
      reducedMotionRef.current = e.matches;
    };
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  // Pulse trigger on data update transition (false → true)
  useEffect(() => {
    if (isUpdating && !prevUpdatingRef.current) {
      setPulseActive(true);
      const t = setTimeout(() => setPulseActive(false), PULSE_DURATION);
      return () => clearTimeout(t);
    }
    prevUpdatingRef.current = isUpdating;
  }, [isUpdating]);

  // Continuous breathe animation via requestAnimationFrame
  const animate = useCallback((time: number) => {
    if (!startTimeRef.current) startTimeRef.current = time;

    const rect = svgRef.current?.querySelector('[data-glow-rect]') as SVGRectElement | null;
    if (!rect) {
      animFrameRef.current = requestAnimationFrame(animate);
      return;
    }

    if (reducedMotionRef.current) {
      rect.setAttribute('opacity', String(OPACITY_STATIC));
    } else {
      const elapsed = time - startTimeRef.current;
      // Sinusoidal oscillation: 0→1→0 over BREATHE_DURATION
      const phase = (elapsed % BREATHE_DURATION) / BREATHE_DURATION;
      const sine = (Math.sin(phase * 2 * Math.PI - Math.PI / 2) + 1) / 2;
      const opacity = OPACITY_MIN + (OPACITY_MAX - OPACITY_MIN) * sine;
      rect.setAttribute('opacity', String(opacity));
    }

    animFrameRef.current = requestAnimationFrame(animate);
  }, []);

  useEffect(() => {
    animFrameRef.current = requestAnimationFrame(animate);
    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
      startTimeRef.current = 0;
    };
  }, [animate]);

  // Confidence maps to gradient spread: higher confidence = wider visible gradient
  const gradientSpread = Math.max(30, Math.min(100, confidence));

  return (
    <svg
      ref={svgRef}
      width="100%"
      height="100%"
      viewBox="0 0 1200 200"
      preserveAspectRatio="none"
      className={className}
      role="img"
      aria-label={`Data confidence horizon: ${confidence}% confidence`}
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="meridian-horizon-gradient" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop
            offset="0%"
            stopColor="var(--brand-tufts, currentColor)"
            stopOpacity={0.6 * (gradientSpread / 100)}
          />
          <stop
            offset="50%"
            stopColor="var(--brand-tufts, currentColor)"
            stopOpacity={0.3 * (gradientSpread / 100)}
          />
          <stop
            offset="100%"
            stopColor="var(--brand-tufts, currentColor)"
            stopOpacity={0}
          />
        </linearGradient>
      </defs>

      {/* Main breathing gradient bar */}
      <rect
        data-glow-rect
        x="0"
        y="0"
        width="1200"
        height="200"
        fill="url(#meridian-horizon-gradient)"
        opacity={OPACITY_STATIC}
      />

      {/* Pulse overlay — brief flash on data update */}
      {pulseActive && (
        <rect
          x="0"
          y="0"
          width="1200"
          height="200"
          fill="var(--brand-tufts, currentColor)"
          opacity={0}
        >
          <animate
            attributeName="opacity"
            values="0.3;0"
            dur={`${PULSE_DURATION}ms`}
            fill="freeze"
            begin="0s"
          />
        </rect>
      )}

      <style>{`
        @media (prefers-reduced-motion: reduce) {
          [data-glow-rect] {
            opacity: ${OPACITY_STATIC} !important;
          }
        }
      `}</style>
    </svg>
  );
}
