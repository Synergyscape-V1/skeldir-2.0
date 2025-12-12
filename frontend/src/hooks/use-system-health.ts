/**
 * System Health Hook - Prism Integration (B0.2)
 * Fetches system health status from Health API (Port 4016)
 * Contract: health.yaml - GET /api/health
 */

import { useQuery } from '@tanstack/react-query';
import { healthService, type HealthStatus } from '@/api/health-client';

export interface UseSystemHealthOptions {
  refetchInterval?: number;
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
 * Fetch system health status from Prism Health API
 */
export function useSystemHealth(
  options: UseSystemHealthOptions = {}
): UseSystemHealthReturn {
  const { refetchInterval = 60000, enabled = true } = options;

  const query = useQuery({
    queryKey: ['/api/health'],
    queryFn: async () => {
      const response = await healthService.getSystemHealth();
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
