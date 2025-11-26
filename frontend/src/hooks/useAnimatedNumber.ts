import { useState, useEffect, useRef } from 'react';

// ============================================================================
// ANIMATED NUMBER HOOK
// ============================================================================

export const useAnimatedNumber = (
  targetValue: number,
  duration: number = 500,
  enabled: boolean = true
): number => {
  const [displayValue, setDisplayValue] = useState(targetValue);
  const animationFrameRef = useRef<number | null>(null);
  const startValueRef = useRef(targetValue);
  const startTimeRef = useRef<number | null>(null);
  
  // Cache reduced motion preference outside of effect to avoid re-evaluation loops
  const prefersReducedMotion = useRef(
    typeof window !== 'undefined' && 
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  );

  useEffect(() => {
    // Skip animation if disabled or reduced motion preferred
    if (!enabled || prefersReducedMotion.current) {
      setDisplayValue(targetValue);
      return;
    }

    // Only animate if value actually changed significantly
    if (Math.abs(targetValue - displayValue) < 0.01) {
      return;
    }

    startValueRef.current = displayValue;
    startTimeRef.current = null;

    const animate = (currentTime: number) => {
      if (startTimeRef.current === null) {
        startTimeRef.current = currentTime;
      }

      const elapsed = currentTime - startTimeRef.current;
      const progress = Math.min(elapsed / duration, 1);

      // Easing function: ease-out cubic
      const easeOutCubic = 1 - Math.pow(1 - progress, 3);

      const currentValue =
        startValueRef.current +
        (targetValue - startValueRef.current) * easeOutCubic;

      setDisplayValue(currentValue);

      if (progress < 1) {
        animationFrameRef.current = requestAnimationFrame(animate);
      } else {
        setDisplayValue(targetValue);
      }
    };

    animationFrameRef.current = requestAnimationFrame(animate);

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [targetValue, duration, enabled]);

  return displayValue;
};
