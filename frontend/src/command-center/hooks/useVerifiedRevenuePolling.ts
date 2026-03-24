import { useEffect, useRef, useState } from 'react';

/** US-style currency, no decimals for dashboard scale. */
export function formatVerifiedUsd(n: number): string {
  return `$${n.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
}

/**
 * Silent poll (default 30s) with smooth interpolation toward new targets.
 * Simulates server pushes with small random walk for demo.
 */
export function useVerifiedRevenuePolling(initialRaw: number, pollIntervalMs = 30_000) {
  const [target, setTarget] = useState(initialRaw);
  const displayRef = useRef(initialRaw);
  const [display, setDisplay] = useState(initialRaw);

  useEffect(() => {
    const id = window.setInterval(() => {
      setTarget((t) => {
        const delta = Math.round((Math.random() - 0.48) * 180);
        return Math.max(0, t + delta);
      });
    }, pollIntervalMs);
    return () => clearInterval(id);
  }, [pollIntervalMs]);

  useEffect(() => {
    const from = displayRef.current;
    const to = target;
    if (from === to) return undefined;

    let start = 0;
    const duration = 600;
    let raf = 0;

    const step = (now: number) => {
      if (!start) start = now;
      const p = Math.min(1, (now - start) / duration);
      const eased = 1 - (1 - p) ** 3;
      const next = Math.round(from + (to - from) * eased);
      displayRef.current = next;
      setDisplay(next);
      if (p < 1) raf = requestAnimationFrame(step);
    };

    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target]);

  return { displayRaw: display, displayFormatted: formatVerifiedUsd(display) };
}
