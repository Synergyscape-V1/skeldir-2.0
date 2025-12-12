/**
 * Async Job Poller Hook
 * Generic hook for polling async job status with exponential backoff
 * B0.2: Supports LLM investigation status polling pattern
 */

import { useState, useEffect, useCallback, useRef } from 'react';

/**
 * Terminal states that stop polling
 */
const TERMINAL_STATES = ['completed', 'failed', 'cancelled'] as const;
type TerminalState = typeof TERMINAL_STATES[number];

/**
 * Polling configuration
 */
const POLLING_CONFIG = {
  initialInterval: 2000,   // 2 seconds
  maxInterval: 10000,      // 10 seconds
  jitterRange: 500,        // ±500ms random jitter
  backoffMultiplier: 1.5,  // Exponential backoff multiplier
} as const;

/**
 * Generic status payload type
 * Must include a 'status' field with possible terminal states
 */
export interface StatusPayload {
  status: string;
  progress?: number;
  error?: {
    code?: string;
    message?: string;
  };
  [key: string]: unknown;
}

/**
 * Hook return type
 */
export interface UseAsyncJobPollerResult<T extends StatusPayload> {
  status: T | null;
  error: Error | null;
  isPolling: boolean;
  refresh: () => void;
}

/**
 * Calculate next interval with exponential backoff and jitter
 */
function calculateNextInterval(currentInterval: number): number {
  const nextInterval = Math.min(
    currentInterval * POLLING_CONFIG.backoffMultiplier,
    POLLING_CONFIG.maxInterval
  );
  
  // Add random jitter ±500ms
  const jitter = (Math.random() - 0.5) * 2 * POLLING_CONFIG.jitterRange;
  return Math.max(POLLING_CONFIG.initialInterval, nextInterval + jitter);
}

/**
 * Check if status is terminal (should stop polling)
 */
function isTerminalState(status: string): status is TerminalState {
  return TERMINAL_STATES.includes(status as TerminalState);
}

/**
 * Hook for polling async job status with exponential backoff
 * 
 * @param jobId - The job ID to poll, or null to disable polling
 * @param fetchStatus - Function to fetch current job status
 * @returns Object with status, error, isPolling flag, and refresh function
 * 
 * @example
 * ```tsx
 * const { status, error, isPolling, refresh } = useAsyncJobPoller(
 *   investigationId,
 *   LLMInvestigationsService.getInvestigationStatus
 * );
 * ```
 */
export function useAsyncJobPoller<T extends StatusPayload>(
  jobId: string | null,
  fetchStatus: (jobId: string) => Promise<T>
): UseAsyncJobPollerResult<T> {
  const [status, setStatus] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [isPolling, setIsPolling] = useState(false);
  
  // Track current interval for backoff
  const intervalRef = useRef<number>(POLLING_CONFIG.initialInterval);
  
  // Track timeout for cleanup
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  
  // Track if component is mounted
  const mountedRef = useRef(true);

  /**
   * Clear any pending timeout
   */
  const clearPendingTimeout = useCallback(() => {
    if (timeoutRef.current !== null) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }, []);

  /**
   * Poll for status
   */
  const poll = useCallback(async () => {
    if (!jobId || !mountedRef.current) {
      return;
    }

    try {
      setIsPolling(true);
      const result = await fetchStatus(jobId);
      
      if (!mountedRef.current) {
        return;
      }

      setStatus(result);
      setError(null);

      // Check if we should continue polling
      if (!isTerminalState(result.status)) {
        // Schedule next poll with backoff
        const nextInterval = calculateNextInterval(intervalRef.current);
        intervalRef.current = nextInterval;
        
        timeoutRef.current = setTimeout(poll, nextInterval);
      } else {
        // Terminal state reached - stop polling
        setIsPolling(false);
      }
    } catch (err) {
      if (!mountedRef.current) {
        return;
      }
      
      setError(err instanceof Error ? err : new Error(String(err)));
      setIsPolling(false);
      
      // On error, still attempt retry with backoff
      const nextInterval = calculateNextInterval(intervalRef.current);
      intervalRef.current = nextInterval;
      
      timeoutRef.current = setTimeout(poll, nextInterval);
    }
  }, [jobId, fetchStatus]);

  /**
   * Force immediate refresh
   */
  const refresh = useCallback(() => {
    clearPendingTimeout();
    intervalRef.current = POLLING_CONFIG.initialInterval;
    poll();
  }, [poll, clearPendingTimeout]);

  /**
   * Effect to start/stop polling based on jobId
   */
  useEffect(() => {
    mountedRef.current = true;
    
    if (jobId) {
      // Reset state for new job
      setStatus(null);
      setError(null);
      intervalRef.current = POLLING_CONFIG.initialInterval;
      
      // Start polling immediately
      poll();
    } else {
      // No job ID - clear state
      setStatus(null);
      setError(null);
      setIsPolling(false);
      clearPendingTimeout();
    }

    // Cleanup on unmount or jobId change
    return () => {
      mountedRef.current = false;
      clearPendingTimeout();
    };
  }, [jobId, poll, clearPendingTimeout]);

  return {
    status,
    error,
    isPolling,
    refresh,
  };
}

export default useAsyncJobPoller;
