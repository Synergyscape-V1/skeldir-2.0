import { useState, useCallback, useRef } from 'react';

type CircuitState = 'closed' | 'open' | 'half-open';
interface RetryConfig { maxRetries?: number; baseDelayMs?: number; isRetriable?: (error: Error | { status?: number }) => boolean; }
interface RetryState { isRetrying: boolean; attemptNumber: number; nextRetryIn: number; retryProgress: number; circuitState: CircuitState; }

const isDefaultRetriable = (error: Error | { status?: number }): boolean => {
  if ('status' in error && typeof error.status === 'number') {
    if (error.status === 429 || error.status >= 500) return true;
    if (error.status >= 400) return false;
  }
  return error instanceof TypeError || (error instanceof Error && (error.name === 'NetworkError' || error.name === 'TimeoutError'));
};

const applyJitter = (delay: number): number => delay * (1 + (Math.random() * 0.4 - 0.2));

export function useRetryLogic(config: RetryConfig = {}) {
  const { maxRetries = 3, baseDelayMs = 1000, isRetriable = isDefaultRetriable } = config;
  const [state, setState] = useState<RetryState>({ isRetrying: false, attemptNumber: 0, nextRetryIn: 0, retryProgress: 0, circuitState: 'closed' });
  const circuitRef = useRef({ consecutiveFailures: 0, openedAt: 0, halfOpenSuccesses: 0, wasHalfOpen: false });

  const executeWithRetry = useCallback(async <T>(fn: () => Promise<T>, correlationId?: string): Promise<T> => {
    const cid = correlationId || crypto.randomUUID?.() || Math.random().toString(36).slice(2);
    const getCircuitState = (): CircuitState => circuitRef.current.consecutiveFailures >= 5 ? (Date.now() - circuitRef.current.openedAt < 30000 ? 'open' : 'half-open') : 'closed';
    
    let currentCircuitState = getCircuitState();
    if (currentCircuitState === 'open') {
      setState(s => ({ ...s, circuitState: 'open' }));
      console.warn(`[${cid}] Circuit breaker OPEN, blocking request`);
      throw new Error('Circuit breaker is open');
    }
    if (currentCircuitState === 'half-open' && !circuitRef.current.wasHalfOpen) {
      setState(s => ({ ...s, circuitState: 'half-open' }));
      circuitRef.current.halfOpenSuccesses = 0;
      circuitRef.current.wasHalfOpen = true;
      console.log(`[${cid}] Circuit breaker entering HALF-OPEN state`);
    }

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        setState(s => ({ ...s, isRetrying: attempt > 0, attemptNumber: attempt, nextRetryIn: 0, retryProgress: attempt / (maxRetries + 1) }));
        console.log(`[${cid}] Attempt ${attempt + 1}/${maxRetries + 1}`);
        const result = await fn();
        
        if (currentCircuitState === 'half-open' && ++circuitRef.current.halfOpenSuccesses >= 2) {
          circuitRef.current.consecutiveFailures = 0;
          circuitRef.current.wasHalfOpen = false;
          currentCircuitState = 'closed';
          console.log(`[${cid}] Circuit breaker CLOSED after successful requests`);
        } else if (currentCircuitState !== 'half-open') circuitRef.current.consecutiveFailures = 0;
        
        setState(s => ({ ...s, isRetrying: false, attemptNumber: 0, nextRetryIn: 0, retryProgress: 1, circuitState: currentCircuitState }));
        return result;
      } catch (error) {
        if (!isRetriable(error as any) || attempt === maxRetries) {
          circuitRef.current.consecutiveFailures++;
          if (circuitRef.current.consecutiveFailures >= 5) {
            circuitRef.current.openedAt = Date.now();
            circuitRef.current.wasHalfOpen = false;
            circuitRef.current.halfOpenSuccesses = 0;
            currentCircuitState = 'open';
            console.error(`[${cid}] Circuit breaker OPENED after 5 consecutive failures`);
          }
          setState(s => ({ ...s, isRetrying: false, attemptNumber: 0, nextRetryIn: 0, retryProgress: 0, circuitState: currentCircuitState }));
          throw error;
        }
        
        const delay = applyJitter(baseDelayMs * Math.pow(2, attempt));
        console.warn(`[${cid}] Retry ${attempt + 1}/${maxRetries} failed, waiting ${delay.toFixed(0)}ms`);
        setState(s => ({ ...s, isRetrying: true, attemptNumber: attempt + 1, nextRetryIn: delay, retryProgress: (attempt + 1) / (maxRetries + 1) }));
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
    throw new Error('Max retries exceeded');
  }, [maxRetries, baseDelayMs, isRetriable]);

  return { executeWithRetry, ...state };
}
