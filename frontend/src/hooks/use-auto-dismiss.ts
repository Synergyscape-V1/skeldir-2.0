import { useState, useEffect, useRef, useCallback } from 'react';

type Severity = 'info' | 'warning' | 'error' | 'critical';
interface UseAutoDismissOptions { severity?: Severity; timeoutMs?: number | null; onDismiss: () => void; onPause?: () => void; onResume?: () => void; }
interface UseAutoDismissReturn { progress: number; remainingMs: number; isPaused: boolean; pause: () => void; resume: () => void; reset: () => void; cancel: () => void; elementRef: React.RefObject<HTMLElement>; }

const TIMEOUTS: Record<Severity, number | null> = { info: 5000, warning: 7000, error: 10000, critical: null };

export function useAutoDismiss({ severity = 'info', timeoutMs, onDismiss, onPause, onResume }: UseAutoDismissOptions): UseAutoDismissReturn {
  const duration = timeoutMs !== undefined ? (timeoutMs === 0 ? null : timeoutMs) : TIMEOUTS[severity];
  const elementRef = useRef<HTMLElement>(null);
  const onDismissRef = useRef(onDismiss);
  const startRef = useRef(0);
  const pausedAtRef = useRef(0);
  const isPausedRef = useRef(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const rafRef = useRef<number | null>(null);
  const dismissedRef = useRef(false);
  const [progress, setProgress] = useState(0);
  const [remainingMs, setRemainingMs] = useState(duration ?? 0);
  const [isPaused, setIsPaused] = useState(false);
  
  useEffect(() => { onDismissRef.current = onDismiss; }, [onDismiss]);

  const updateProgress = useCallback(() => {
    if (!duration || isPausedRef.current) return;
    const elapsed = performance.now() - startRef.current;
    setProgress(Math.min(elapsed / duration, 1));
    setRemainingMs(Math.max(duration - elapsed, 0));
    if (elapsed < duration) rafRef.current = requestAnimationFrame(updateProgress);
  }, [duration]);

  const pause = useCallback(() => {
    if (!duration || isPausedRef.current) return;
    if (timerRef.current) clearTimeout(timerRef.current);
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    pausedAtRef.current = performance.now() - startRef.current;
    isPausedRef.current = true;
    setIsPaused(true);
    onPause?.();
  }, [duration, onPause]);

  const resume = useCallback(() => {
    if (!duration || !isPausedRef.current) return;
    startRef.current = performance.now() - pausedAtRef.current;
    isPausedRef.current = false;
    setIsPaused(false);
    timerRef.current = setTimeout(() => !dismissedRef.current && (dismissedRef.current = true, onDismissRef.current()), duration - pausedAtRef.current);
    rafRef.current = requestAnimationFrame(updateProgress);
    onResume?.();
  }, [duration, updateProgress, onResume]);

  const reset = useCallback(() => {
    if (!duration) return;
    if (timerRef.current) clearTimeout(timerRef.current);
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    dismissedRef.current = false; pausedAtRef.current = 0;
    isPausedRef.current = false; setProgress(0); setRemainingMs(duration); setIsPaused(false);
    startRef.current = performance.now();
    timerRef.current = setTimeout(() => !dismissedRef.current && (dismissedRef.current = true, onDismissRef.current()), duration);
    rafRef.current = requestAnimationFrame(updateProgress);
  }, [duration, updateProgress]);

  const cancel = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    dismissedRef.current = true;
  }, []);

  useEffect(() => {
    if (!duration) return;
    startRef.current = performance.now();
    timerRef.current = setTimeout(() => !dismissedRef.current && (dismissedRef.current = true, onDismissRef.current()), duration);
    rafRef.current = requestAnimationFrame(updateProgress);
    return () => { if (timerRef.current) clearTimeout(timerRef.current); if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, [duration, updateProgress]);

  useEffect(() => {
    const el = elementRef.current; if (!el) return;
    el.addEventListener('mouseenter', pause); el.addEventListener('mouseleave', resume);
    el.addEventListener('focusin', pause); el.addEventListener('focusout', resume);
    return () => { el.removeEventListener('mouseenter', pause); el.removeEventListener('mouseleave', resume); el.removeEventListener('focusin', pause); el.removeEventListener('focusout', resume); };
  }, [pause, resume]);

  return { progress, remainingMs, isPaused, pause, resume, reset, cancel, elementRef };
}
