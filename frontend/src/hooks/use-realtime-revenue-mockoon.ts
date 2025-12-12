/**
 * Realtime Revenue Hook - Prism Integration (B0.2)
 * Fetches revenue data from Attribution API (Port 4011)
 * Contract: attribution.yaml - GET /api/attribution/revenue/realtime
 */

import { useQuery } from '@tanstack/react-query';
import { attributionClient } from '@/api/attribution-client';
import type { RevenueRealtimeResponse, RevenueRealtimeResponseB2_6 } from '@/api/attribution-client';

export interface UseRealtimeRevenueOptions {
  refetchInterval?: number; // Polling interval in milliseconds (default: 30000)
  enabled?: boolean;
}

export interface UseRealtimeRevenueReturn {
  data: RevenueRealtimeResponse | RevenueRealtimeResponseB2_6 | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
  correlationId?: string;
}

/**
 * Fetch realtime revenue data from Mockoon Attribution API
 * Supports both B0.6 (interim) and B2.6 (final) response schemas
 */
export function useRealtimeRevenue(
  options: UseRealtimeRevenueOptions = {}
): UseRealtimeRevenueReturn {
  const { refetchInterval = 30000, enabled = true } = options;

  const query = useQuery({
    queryKey: ['/api/attribution/revenue/realtime'],
    queryFn: async () => {
      const response = await attributionClient.getRealtimeRevenue();
      
      if (response.error) {
        throw new Error(response.error.detail || 'Failed to fetch realtime revenue');
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

  return {
    data: query.data?.data || null,
    isLoading: query.isLoading,
    error: query.error instanceof Error ? query.error : null,
    refetch: query.refetch,
    correlationId: query.data?.correlationId,
  };
}
