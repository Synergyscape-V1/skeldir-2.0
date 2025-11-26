/**
 * Dashboard Polling Hook
 * Implements automatic polling for dashboard data per Architecture Guide FE-1.3
 * Polls every 30 seconds as required
 * Integrates error banner system per Architecture Guide FE-1.5
 */

import { useEffect, useCallback } from 'react';
import { usePollingManager } from './use-polling-manager';
import { useDashboardStore } from '@/stores/dashboard.store';
import { useApiClientWithBanners } from './use-api-client-with-banners';
import type { ApiClient } from '@/services/attribution.service';

export function useDashboardPolling() {
  // Use API client with automatic error banner integration
  // Per Architecture Guide FE-1.5: Display error banners within 60s of backend failure
  const apiClient = useApiClientWithBanners({
    retries: 3,
    exponentialBackoff: true,
    baseDelayMs: 1000,
    maxDelayMs: 8000
  }) as ApiClient;
  
  const { loadActivity, retryActivity } = useDashboardStore();
  
  // Memoize polling callback to prevent interval accumulation
  // Note: loadActivity is from Zustand and is stable, but ESLint requires it in deps
  // We use eslint-disable to avoid infinite loops from Zustand's function references
  const handlePoll = useCallback(async () => {
    // Poll activity data using service layer via store
    // Errors automatically trigger banners via useApiClientWithBanners
    await loadActivity(apiClient);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiClient]);
  
  // Memoize state change callback to prevent unnecessary re-renders
  const handleStateChange = useCallback((state: any) => {
    if (import.meta.env.DEV) {
      console.log('[DashboardPolling] Polling state changed:', {
        isPaused: state.isPaused,
        isPausedByVisibility: state.isPausedByVisibility,
        isActive: state.isActive
      });
    }
  }, []);
  
  const { isPaused, isActive } = usePollingManager({
    intervalMs: 30000, // 30 seconds as per Architecture Guide FE-1.3
    onPoll: handlePoll,
    onStateChange: handleStateChange
  });
  
  // Initial load on mount
  useEffect(() => {
    loadActivity(apiClient);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  
  // Provide retry function that already has apiClient bound
  const retry = useCallback(() => retryActivity(apiClient), [apiClient]);
  
  return {
    isPolling: isActive && !isPaused,
    isPaused,
    isActive,
    retry
  };
}
