/**
 * System Health Hook - Mockoon Integration
 * Fetches system health status from Health API (Port 4014)
 * Contract: health.yaml - GET /api/health
 */

import { useQuery } from '@tanstack/react-query';
import { healthClient, type HealthStatus } from '@/api/health-client';

export interface UseSystemHealthOptions {
  refetchInterval?: number; // Polling interval in milliseconds (default: 60000)
  enabled?: boolean;
}

export interface UseSystemHealthReturn {
  data: HealthStatus | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
  correlationId?: string;
  isHealthy: boolean;
  isDegraded: boolean;
  isUnhealthy: boolean;
}

/**
 * Fetch system health status from Mockoon Health API
 */
export function useSystemHealth(
  options: UseSystemHealthOptions = {}
): UseSystemHealthReturn {
  const { refetchInterval = 60000, enabled = true } = options;

  const query = useQuery({
    queryKey: ['/api/health'],
    queryFn: async () => {
      const response = await healthClient.getSystemHealth();
      
      if (response.error) {
        throw new Error(response.error.detail || 'Failed to fetch system health');
      }

      return {
        data: response.data,
        correlationId: response.correlationId,
      };
    },
    refetchInterval: enabled ? refetchInterval : false,
    enabled,
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
  });

  const data = query.data?.data || null;

  return {
    data,
    isLoading: query.isLoading,
    error: query.error instanceof Error ? query.error : null,
    refetch: query.refetch,
    correlationId: query.data?.correlationId,
    isHealthy: data?.status === 'healthy',
    isDegraded: data?.status === 'degraded',
    isUnhealthy: data?.status === 'unhealthy',
  };
}
