/**
 * Example integrations for useRetryLogic hook
 * Shows how to integrate with ApiClient and standalone usage
 */

import { useState, useEffect } from 'react';
import { useRetryLogic } from './use-retry-logic';
import { useApiClient } from './use-api-client';

/**
 * Example 1: Standalone usage with fetch
 */
export function useRetryFetch() {
  const { executeWithRetry, ...retryState } = useRetryLogic({
    maxRetries: 3,
    baseDelayMs: 1000,
  });

  const fetchWithRetry = async <T>(url: string, options?: RequestInit): Promise<T> => {
    return executeWithRetry(async () => {
      const response = await fetch(url, options);
      if (!response.ok) {
        throw { status: response.status, message: response.statusText };
      }
      return response.json();
    });
  };

  return { fetchWithRetry, ...retryState };
}

/**
 * Example 2: Integration with existing ApiClient
 * Wraps ApiClient requests with retry logic
 */
export function useApiClientWithRetry() {
  const apiClient = useApiClient();
  const { executeWithRetry, ...retryState } = useRetryLogic();

  const enhancedClient = {
    get: async <T>(url: string, opts?: any) => {
      return executeWithRetry(() => apiClient.get<T>(url, opts));
    },
    post: async <TReq, TRes>(url: string, body?: TReq, opts?: any) => {
      return executeWithRetry(() => apiClient.post<TReq, TRes>(url, body, opts));
    },
    put: async <TReq, TRes>(url: string, body?: TReq, opts?: any) => {
      return executeWithRetry(() => apiClient.put<TReq, TRes>(url, body, opts));
    },
    patch: async <TReq, TRes>(url: string, body?: TReq, opts?: any) => {
      return executeWithRetry(() => apiClient.patch<TReq, TRes>(url, body, opts));
    },
    delete: async <TRes>(url: string, opts?: any) => {
      return executeWithRetry(() => apiClient.delete<TRes>(url, opts));
    },
  };

  return { ...enhancedClient, ...retryState };
}

/**
 * Example 3: Custom error classification for domain-specific errors
 */
export function useDomainRetryLogic() {
  const { executeWithRetry, ...retryState } = useRetryLogic({
    maxRetries: 5,
    baseDelayMs: 2000,
    isRetriable: (error: any) => {
      // Custom business logic for retrying
      if (error.code === 'TEMPORARY_LOCK') return true;
      if (error.code === 'RESOURCE_BUSY') return true;
      if (error.status === 503) return true;
      if (error.status === 429) return true;
      return false;
    },
  });

  return { executeWithRetry, ...retryState };
}

/**
 * Example 4: Component usage with UI feedback
 */
export function useDataFetchWithRetry<T>(url: string, enabled: boolean = true) {
  const { executeWithRetry, isRetrying, attemptNumber, retryProgress, circuitState } = useRetryLogic();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!enabled) return;

    executeWithRetry(async () => {
      const response = await fetch(url);
      if (!response.ok) throw { status: response.status };
      return response.json();
    })
      .then(setData)
      .catch(setError);
  }, [url, enabled, executeWithRetry]);

  return {
    data,
    error,
    isRetrying,
    attemptNumber,
    retryProgress,
    circuitState,
    isLoading: !data && !error && !isRetrying,
  };
}

/**
 * Example 5: Manual retry with correlation ID tracking
 */
export function useTrackedRetry() {
  const { executeWithRetry, ...retryState } = useRetryLogic();

  const executeWithTracking = async <T>(
    fn: () => Promise<T>,
    operationName: string
  ): Promise<T> => {
    const correlationId = `${operationName}-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    console.log(`[${correlationId}] Starting operation: ${operationName}`);

    try {
      const result = await executeWithRetry(fn, correlationId);
      console.log(`[${correlationId}] Operation succeeded`);
      return result;
    } catch (error) {
      console.error(`[${correlationId}] Operation failed:`, error);
      throw error;
    }
  };

  return { executeWithTracking, ...retryState };
}
