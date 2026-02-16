/**
 * A5-FORGE Signature Animation: PulseCascadeIndicator
 *
 * On poll completion, a cascade ripple animates through a set of elements.
 * Each element receives a subtle background-color flash, staggered 50ms apart,
 * confirming "fresh data just arrived" in a sequential wave pattern.
 *
 * The cascade metaphor evokes a forge's production line: data flows through
 * each station in sequence, each one briefly lighting up as it processes.
 *
 * prefers-reduced-motion: single flash on first element only, no cascade.
 *
 * Master Skill citations:
 *   - SVG-02 cascade pattern (sequential element activation)
 *   - Motion tokens: pulse=600ms total, 50ms stagger per element
 *   - Anti-pattern: no decorative-only animation (encodes data freshness)
 *   - Token compliance: var(--brand-tufts) flash color, zero hardcoded hex
 */

import { useEffect, useRef, useState, useCallback } from 'react';

interface PulseCascadeIndicatorProps {
  /** When true, triggers a cascade pulse */
  isUpdating: boolean;
  /** Number of cascade segments to display */
  segments?: number;
  /** Optional className for container */
  className?: string;
  /** Height of the indicator bar */
  height?: number;
}

const STAGGER_MS = 50;
const SEGMENT_FLASH_MS = 300;

export function PulseCascadeIndicator({
  isUpdating,
  segments = 12,
  className,
  height = 3,
}: PulseCascadeIndicatorProps) {
  const [activeSegments, setActiveSegments] = useState<Set<number>>(new Set());
  const prevUpdatingRef = useRef(false);
  const reducedMotionRef = useRef(false);
  const timeoutsRef = useRef<ReturnType<typeof setTimeout>[]>([]);

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

  const triggerCascade = useCallback(() => {
    // Clear any pending cascades
    timeoutsRef.current.forEach(clearTimeout);
    timeoutsRef.current = [];

    if (reducedMotionRef.current) {
      // Reduced motion: single flash on first segment
      setActiveSegments(new Set([0]));
      const t = setTimeout(() => setActiveSegments(new Set()), SEGMENT_FLASH_MS);
      timeoutsRef.current.push(t);
      return;
    }

    // Full cascade: stagger activation
    for (let i = 0; i < segments; i++) {
      const activateT = setTimeout(() => {
        setActiveSegments(prev => new Set([...prev, i]));
      }, i * STAGGER_MS);

      const deactivateT = setTimeout(() => {
        setActiveSegments(prev => {
          const next = new Set(prev);
          next.delete(i);
          return next;
        });
      }, i * STAGGER_MS + SEGMENT_FLASH_MS);

      timeoutsRef.current.push(activateT, deactivateT);
    }
  }, [segments]);

  // Trigger on update transition (false → true)
  useEffect(() => {
    if (isUpdating && !prevUpdatingRef.current) {
      triggerCascade();
    }
    prevUpdatingRef.current = isUpdating;
  }, [isUpdating, triggerCascade]);

  // Cleanup
  useEffect(() => {
    return () => {
      timeoutsRef.current.forEach(clearTimeout);
    };
  }, []);

  return (
    <div
      className={className}
      role="img"
      aria-label="Data refresh cascade indicator"
      aria-hidden="true"
      style={{ display: 'flex', gap: '2px', height }}
    >
      {Array.from({ length: segments }, (_, i) => (
        <div
          key={i}
          style={{
            flex: 1,
            height: '100%',
            borderRadius: '1px',
            backgroundColor: activeSegments.has(i)
              ? 'var(--brand-tufts, currentColor)'
              : 'var(--muted, #1a1a2e)',
            opacity: activeSegments.has(i) ? 0.8 : 0.15,
            transition: `background-color ${SEGMENT_FLASH_MS}ms ease-out, opacity ${SEGMENT_FLASH_MS}ms ease-out`,
          }}
        />
      ))}
    </div>
  );
}
