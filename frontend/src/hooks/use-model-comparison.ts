/**
 * Model Comparison Hook - Mockoon Integration
 * Fetches model comparison data from Attribution API (Port 4011)
 * Contract: attribution.yaml - GET /api/attribution/models/compare
 */

import { useQuery } from '@tanstack/react-query';
import { attributionClient, type ModelComparison } from '@/api/attribution-client';

export interface UseModelComparisonOptions {
  enabled?: boolean;
}

export interface UseModelComparisonReturn {
  data: ModelComparison[] | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
  correlationId?: string;
}

/**
 * Fetch model comparison data from Mockoon Attribution API
 * Compares different attribution models (first-touch, last-touch, linear, etc.)
 */
export function useModelComparison(
  options: UseModelComparisonOptions = {}
): UseModelComparisonReturn {
  const { enabled = true } = options;

  const query = useQuery({
    queryKey: ['/api/attribution/models/compare'],
    queryFn: async () => {
      const response = await attributionClient.compareModels();
      
      if (response.error) {
        throw new Error(response.error.detail || 'Failed to fetch model comparison');
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
