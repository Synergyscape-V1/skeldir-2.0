import { useState, useEffect, useCallback, useRef } from 'react';

interface AutoRefreshConfig {
  enabled: boolean; // Auto-refresh only when match < 100%
  intervalMs: number; // Polling interval (default: 30000ms = 30s)
  onRefresh: () => Promise<void>; // Async function to fetch fresh data
  onError?: (error: Error) => void; // Error handler
}

interface AutoRefreshState {
  isRefreshing: boolean;
  lastRefreshTime: Date | null;
  nextRefreshIn: number; // Seconds until next refresh
  error: Error | null;
  refreshCount: number; // Total refreshes this session
}

export const useReconciliationAutoRefresh = ({
  enabled,
  intervalMs = 30000,
  onRefresh,
  onError,
}: AutoRefreshConfig) => {
  const [state, setState] = useState<AutoRefreshState>({
    isRefreshing: false,
    lastRefreshTime: null,
    nextRefreshIn: Math.floor(intervalMs / 1000),
    error: null,
    refreshCount: 0,
  });

  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const countdownRef = useRef<NodeJS.Timeout | null>(null);

  // Manual refresh function
  const triggerRefresh = useCallback(async () => {
    // Use functional setState to check and set isRefreshing atomically
    let shouldExecute = false;
    
    setState(prev => {
      if (prev.isRefreshing) {
        shouldExecute = false;
        return prev; // Already refreshing, don't modify state
      }
      shouldExecute = true;
      return { ...prev, isRefreshing: true, error: null };
    });

    // Only proceed if we successfully set isRefreshing to true
    if (!shouldExecute) return;

    try {
      await onRefresh();
      setState(prev => ({
        ...prev,
        isRefreshing: false,
        lastRefreshTime: new Date(),
        refreshCount: prev.refreshCount + 1,
        nextRefreshIn: Math.floor(intervalMs / 1000),
      }));
    } catch (error) {
      const err = error instanceof Error ? error : new Error('Refresh failed');
      setState(prev => ({ ...prev, isRefreshing: false, error: err }));
      onError?.(err);
    }
  }, [onRefresh, onError, intervalMs]);

  // Countdown timer for "Next refresh in X seconds"
  useEffect(() => {
    if (!enabled || state.isRefreshing) return;

    countdownRef.current = setInterval(() => {
      setState(prev => {
        const nextValue = prev.nextRefreshIn - 1;
        return {
          ...prev,
          nextRefreshIn: nextValue >= 0 ? nextValue : Math.floor(intervalMs / 1000),
        };
      });
    }, 1000);

    return () => {
      if (countdownRef.current) clearInterval(countdownRef.current);
    };
  }, [enabled, state.isRefreshing, intervalMs]);

  // Automatic polling interval
  useEffect(() => {
    if (!enabled) {
      // Clear any existing intervals when disabled
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      return;
    }

    // Initial refresh on mount (if enabled)
    triggerRefresh();

    // Set up polling interval
    intervalRef.current = setInterval(() => {
      triggerRefresh();
    }, intervalMs);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [enabled, intervalMs, triggerRefresh]);

  return {
    ...state,
    triggerRefresh, // Manual refresh function
    resetError: () => setState(prev => ({ ...prev, error: null })),
  };
};
