/**
 * Channel Performance Hook - Mockoon Integration
 * Fetches channel performance data from Attribution API (Port 4011)
 * Contract: attribution.yaml - GET /api/attribution/channels
 */

import { useQuery } from '@tanstack/react-query';
import { attributionClient, type ChannelPerformance } from '@/api/attribution-client';

export interface UseChannelPerformanceOptions {
  enabled?: boolean;
}

export interface UseChannelPerformanceReturn {
  data: ChannelPerformance[] | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
  correlationId?: string;
}

/**
 * Fetch channel performance data from Mockoon Attribution API
 * B2.6 schema - returns root-level array
 */
export function useChannelPerformance(
  options: UseChannelPerformanceOptions = {}
): UseChannelPerformanceReturn {
  const { enabled = true } = options;

  const query = useQuery({
    queryKey: ['/api/attribution/channels'],
    queryFn: async () => {
      const response = await attributionClient.getChannelPerformance();
      
      if (response.error) {
        throw new Error(response.error.detail || 'Failed to fetch channel performance');
      }

      return {
        data: response.data,
        correlationId: response.correlationId,
      };
    },
    enabled,
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
  });

  return {
    data: query.data?.data || null,
    isLoading: query.isLoading,
    error: query.error instanceof Error ? query.error : null,
    refetch: query.refetch,
    correlationId: query.data?.correlationId,
  };
}
