/**
 * Command Center Polling Hook — Final Production Implementation
 *
 * Wraps shared usePollingManager:
 * - 30s interval for dashboard metrics
 * - 5min (300s) interval for channel performance
 * - Returns isUpdating flag for EvidenceAccumulatorRing pulse
 * - Deterministic fixture data until backend connection
 *
 * Architecture compliance:
 *   - All data fetching in hooks, never in components
 *   - No UI business logic — returns backend-shaped data as-is
 *   - Silent updates: no status transition, no flicker
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { usePollingManager } from '@/hooks/use-polling-manager';
import { type CommandCenterState, FIXTURES } from './types';

interface CommandCenterPollingResult {
  state: CommandCenterState;
  isPolling: boolean;
  isUpdating: boolean;
  lastUpdated: Date | null;
  retry: () => void;
}

export function useCommandCenterPolling(): CommandCenterPollingResult {
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
    // Signal update pulse for EvidenceAccumulatorRing
    setIsUpdating(true);
    if (updateTimeoutRef.current) clearTimeout(updateTimeoutRef.current);
    updateTimeoutRef.current = setTimeout(() => setIsUpdating(false), 600);

    // In production: fetch from /api/v1/dashboard/summary
    // For now: silent update — refresh timestamp without flicker
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

  // channelPolling is active via side effects
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
    retry,
  };
}
