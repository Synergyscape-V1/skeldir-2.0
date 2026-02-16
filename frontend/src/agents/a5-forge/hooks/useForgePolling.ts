/**
 * A5-FORGE Polling Hook
 *
 * Wraps shared usePollingManager for Forge's data-forward tabular layout.
 * - 30s interval for dashboard metrics
 * - 5min (300s) interval for channel performance
 * - Returns isUpdating flag for PulseCascadeIndicator
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { usePollingManager } from '@/hooks/use-polling-manager';
import { type CommandCenterState, FIXTURES } from '../types';

interface ForgePollingResult {
  state: CommandCenterState;
  isPolling: boolean;
  isUpdating: boolean;
  lastUpdated: Date | null;
  pollCount: number;
  retry: () => void;
}

export function useForgePolling(): ForgePollingResult {
  const [state, setState] = useState<CommandCenterState>({ status: 'loading' });
  const [isUpdating, setIsUpdating] = useState(false);
  const updateTimeoutRef = useRef<ReturnType<typeof setTimeout>>();

  // Simulate initial load → ready transition (1200ms)
  useEffect(() => {
    const timer = setTimeout(() => {
      setState(FIXTURES.ready);
    }, 1200);
    return () => clearTimeout(timer);
  }, []);

  const handleDashboardPoll = useCallback(async () => {
    // Signal update pulse for PulseCascadeIndicator
    setIsUpdating(true);
    if (updateTimeoutRef.current) clearTimeout(updateTimeoutRef.current);
    updateTimeoutRef.current = setTimeout(() => setIsUpdating(false), 600);

    // Silent update — no status transition, no flicker
    setState((prev) => {
      if (prev.status !== 'ready') return prev;
      return {
        ...prev,
        data: {
          ...prev.data,
          lastUpdated: new Date().toISOString(),
        },
      };
    });
  }, []);

  const handleChannelPoll = useCallback(async () => {
    // In production: fetch from /api/v1/channels/performance
  }, []);

  const dashboardPolling = usePollingManager({
    intervalMs: 30_000,
    onPoll: handleDashboardPoll,
  });

  const channelPolling = usePollingManager({
    intervalMs: 300_000,
    onPoll: handleChannelPoll,
  });

  void channelPolling;

  const retry = useCallback(() => {
    setState({ status: 'loading' });
    setTimeout(() => {
      setState(FIXTURES.ready);
    }, 800);
  }, []);

  return {
    state,
    isPolling: dashboardPolling.isActive,
    isUpdating,
    lastUpdated: dashboardPolling.lastPollTime,
    pollCount: dashboardPolling.pollCount,
    retry,
  };
}
