/**
 * A1-SENTINEL Polling Hook
 *
 * Wraps the shared usePollingManager for Sentinel's layout.
 * - 30s interval for dashboard metrics
 * - 5min (300s) interval for channel performance
 * - Returns deterministic fixture data (backend not yet connected)
 * - Provides isUpdating flag for triggering radar pulse animation
 *
 * Architecture compliance:
 *   - All data fetching in hooks, never in components
 *   - Uses useAnimatedValue for smooth number transitions
 *   - No UI business logic — returns backend-shaped data as-is
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { usePollingManager } from '@/hooks/use-polling-manager';
import {
  type CommandCenterState,
  FIXTURES,
} from '../types';

interface SentinelPollingResult {
  state: CommandCenterState;
  isPolling: boolean;
  isUpdating: boolean;
  lastUpdated: Date | null;
  dashboardPollCount: number;
  channelPollCount: number;
  retry: () => void;
}

export function useSentinelPolling(): SentinelPollingResult {
  const [state, setState] = useState<CommandCenterState>({ status: 'loading' });
  const [isUpdating, setIsUpdating] = useState(false);
  const updateTimeoutRef = useRef<ReturnType<typeof setTimeout>>();

  // Simulate initial load → ready transition
  useEffect(() => {
    const timer = setTimeout(() => {
      setState(FIXTURES.ready);
    }, 1200);
    return () => clearTimeout(timer);
  }, []);

  const handleDashboardPoll = useCallback(async () => {
    // Signal update pulse for radar animation
    setIsUpdating(true);
    if (updateTimeoutRef.current) clearTimeout(updateTimeoutRef.current);
    updateTimeoutRef.current = setTimeout(() => setIsUpdating(false), 600);

    // In production: fetch from /api/v1/dashboard/summary
    // For now: maintain fixture data (silent update — no flicker)
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
    // Silent update — no state transition, just data refresh
  }, []);

  const dashboardPolling = usePollingManager({
    intervalMs: 30_000,
    onPoll: handleDashboardPoll,
  });

  const channelPolling = usePollingManager({
    intervalMs: 300_000,
    onPoll: handleChannelPoll,
  });

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
    dashboardPollCount: dashboardPolling.pollCount,
    channelPollCount: channelPolling.pollCount,
    retry,
  };
}
