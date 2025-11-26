/**
 * Reconciliation Status Hook - Mockoon Integration
 * Fetches reconciliation status from Reconciliation API (Port 4012)
 * Contract: reconciliation.yaml - GET /api/reconciliation/status
 */

import { useQuery } from '@tanstack/react-query';
import { reconciliationClient, type ReconciliationStatus } from '@/api/reconciliation-client';

export interface UseReconciliationStatusOptions {
  refetchInterval?: number; // Polling interval in milliseconds
  enabled?: boolean;
}

export interface UseReconciliationStatusReturn {
  data: ReconciliationStatus | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
  correlationId?: string;
}

/**
 * Fetch reconciliation status from Mockoon Reconciliation API
 */
export function useReconciliationStatus(
  options: UseReconciliationStatusOptions = {}
): UseReconciliationStatusReturn {
  const { refetchInterval, enabled = true } = options;

  const query = useQuery({
    queryKey: ['/api/reconciliation/status'],
    queryFn: async () => {
      const response = await reconciliationClient.getStatus();
      
      if (response.error) {
        throw new Error(response.error.detail || 'Failed to fetch reconciliation status');
      }

      return {
        data: response.data,
        correlationId: response.correlationId,
      };
    },
    refetchInterval: enabled && refetchInterval ? refetchInterval : false,
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
