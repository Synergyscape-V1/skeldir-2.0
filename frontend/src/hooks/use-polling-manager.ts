import { useState, useEffect, useRef, useCallback } from 'react';

export interface PollingState {
  isPaused: boolean;
  isPausedByVisibility: boolean;
  isActive: boolean;
  timeUntilNext: number;
  lastPollTime: Date | null;
  pollCount: number;
}

export function usePollingManager({ intervalMs = 30000, onPoll, onStateChange }: { 
  intervalMs?: number; 
  onPoll: () => void | Promise<void>; 
  onStateChange?: (state: PollingState) => void;
}) {
  const [isPaused, setIsPaused] = useState(false);
  const [isPausedByVisibility, setIsPausedByVisibility] = useState(false);
  const [timeUntilNext, setTimeUntilNext] = useState(intervalMs);
  const [lastPollTime, setLastPollTime] = useState<Date | null>(null);
  const [pollCount, setPollCount] = useState(0);
  const intervalRef = useRef<number>();
  const countdownRef = useRef<number>();
  const nextExecutionRef = useRef(Date.now() + intervalMs);
  const isPollingRef = useRef(false);

  const executePoll = useCallback(async () => {
    if (isPollingRef.current) return;
    isPollingRef.current = true;
    try {
      await onPoll();
      setLastPollTime(new Date());
      setPollCount(c => c + 1);
    } finally { isPollingRef.current = false; }
  }, [onPoll]);

  const scheduleNext = useCallback(() => {
    const now = Date.now();
    
    // Calculate next execution time safely without loops to prevent browser freeze
    if (nextExecutionRef.current <= now) {
      const missedIntervals = Math.floor((now - nextExecutionRef.current) / intervalMs) + 1;
      nextExecutionRef.current += missedIntervals * intervalMs;
    }
    
    const adjustedInterval = Math.max(100, nextExecutionRef.current - now);
    
    if (intervalRef.current) clearInterval(intervalRef.current);
    intervalRef.current = window.setInterval(async () => { 
      await executePoll(); 
      scheduleNext(); 
    }, adjustedInterval);
  }, [intervalMs, executePoll]);

  const isActive = !isPaused && !isPausedByVisibility;

  useEffect(() => {
    const handleVisibility = () => {
      setIsPausedByVisibility(document.hidden);
      if (!document.hidden && !isPaused) executePoll();
    };
    document.addEventListener('visibilitychange', handleVisibility);
    return () => document.removeEventListener('visibilitychange', handleVisibility);
  }, [isPaused, executePoll]);

  useEffect(() => {
    if (isActive) {
      (async () => {
        await executePoll();
        scheduleNext();
      })();
      countdownRef.current = window.setInterval(() => setTimeUntilNext(Math.max(0, nextExecutionRef.current - Date.now())), 1000);
    }
    
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
      if (countdownRef.current) clearInterval(countdownRef.current);
    };
  }, [isActive, scheduleNext, executePoll]);

  useEffect(() => onStateChange?.({ isPaused, isPausedByVisibility, isActive, timeUntilNext, lastPollTime, pollCount }), 
    [isPaused, isPausedByVisibility, isActive, timeUntilNext, lastPollTime, pollCount, onStateChange]);

  return {
    pause: useCallback(() => setIsPaused(true), []),
    resume: useCallback(() => setIsPaused(false), []),
    toggle: useCallback(() => setIsPaused(p => !p), []),
    isPaused, isPausedByVisibility, isActive, timeUntilNext, lastPollTime, pollCount
  };
}
