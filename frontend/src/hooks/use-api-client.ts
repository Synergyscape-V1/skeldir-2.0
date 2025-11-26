import { useMemo } from 'react';
import { tokenManager } from '@/lib/token-manager';

export interface ApiError {
  status: number;
  code?: string;
  message: string;
  details?: unknown;
  correlationId?: string;
}

export interface ApiResponse<T> {
  data: T | null;
  error: ApiError | null;
  correlationId?: string;
}

export type RequestInterceptor = (ctx: { url: string; init: RequestInit }) => Promise<{ url: string; init: RequestInit }> | { url: string; init: RequestInit };
export type ResponseInterceptor = (ctx: { response: Response; correlationId: string }) => Promise<Response> | Response;

export interface ApiClientConfig {
  baseUrl?: string;
  retries?: number;
  delaysMs?: number[];
  exponentialBackoff?: boolean;
  baseDelayMs?: number;
  maxDelayMs?: number;
  requestInterceptors?: RequestInterceptor[];
  responseInterceptors?: ResponseInterceptor[];
}

const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));
const parseJsonSafe = async (res: Response): Promise<unknown> => {
  try { return await res.json(); } catch { return null; }
};

// ========== ROOT CAUSE FIX ==========
// Use stable empty arrays to prevent breaking memoization on every hook invocation
// Creating new arrays on each render causes infinite re-render loops
const EMPTY_INTERCEPTORS: RequestInterceptor[] = [];
const EMPTY_RESPONSE_INTERCEPTORS: ResponseInterceptor[] = [];
// ====================================

export function useApiClient(config?: ApiClientConfig) {
  const baseUrl = config?.baseUrl || '';
  const maxRetries = config?.retries ?? 3;
  const legacyDelays = config?.delaysMs;
  const useExponentialBackoff = config?.exponentialBackoff ?? true;
  const baseDelayMs = config?.baseDelayMs ?? 1000;
  const maxDelayMs = config?.maxDelayMs ?? 32000;
  const requestInterceptors = config?.requestInterceptors ?? EMPTY_INTERCEPTORS;
  const responseInterceptors = config?.responseInterceptors ?? EMPTY_RESPONSE_INTERCEPTORS;

  const request = useMemo(() => async <TReq = unknown, TRes = unknown>(
    method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE',
    url: string,
    opts?: { body?: TReq; headers?: Record<string, string>; signal?: AbortSignal }
  ): Promise<ApiResponse<TRes>> => {
    const correlationId = crypto.randomUUID?.() || Math.random().toString(36).slice(2);
    const fullUrl = baseUrl + url;
    
    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      const startTime = performance.now();
      
      try {
        // Task 1: Safe TokenManager access with exception handling
        let authHeader: { Authorization?: string } = {};
        try {
          authHeader = await tokenManager.getAuthHeader();
        } catch (tokenError) {
          console.warn(`[${correlationId}] TokenManager not initialized, proceeding without auth header`);
        }

        let requestInit: RequestInit = {
          method,
          headers: {
            ...authHeader,
            'X-Correlation-Id': correlationId,
            ...(opts?.body && { 'Content-Type': 'application/json' }),
            ...opts?.headers,
          },
          credentials: 'include',
          signal: opts?.signal,
          ...(opts?.body && { body: JSON.stringify(opts.body) }),
        };

        let requestUrl = fullUrl;
        for (const interceptor of requestInterceptors) {
          const result = await interceptor({ url: requestUrl, init: requestInit });
          requestUrl = result.url;
          requestInit = result.init;
        }

        // Task 3: Log request initiation
        console.log(`[${correlationId}] → ${method} ${requestUrl} (attempt ${attempt + 1}/${maxRetries + 1})`);

        let response = await fetch(requestUrl, requestInit);

        for (const interceptor of responseInterceptors) {
          response = await interceptor({ response, correlationId });
        }

        const serverCorrelationId = response.headers.get('x-correlation-id') || correlationId;
        const elapsedMs = Math.round(performance.now() - startTime);

        // Task 3: Log response received
        console.log(`[${correlationId}] ← ${response.status} ${response.statusText} (${elapsedMs}ms)`);

        // Task 2: Exponential backoff for 429 responses
        if (response.status === 429) {
          if (attempt < maxRetries) {
            let delayMs: number;
            
            if (legacyDelays) {
              // Use legacy custom delays if provided
              delayMs = legacyDelays[attempt] || legacyDelays[legacyDelays.length - 1];
            } else if (useExponentialBackoff) {
              // True exponential backoff: baseDelay * 2^attempt with cap
              delayMs = Math.min(baseDelayMs * Math.pow(2, attempt), maxDelayMs);
            } else {
              // Fallback to base delay
              delayMs = baseDelayMs;
            }

            // Task 3: Log 429 retry event
            console.warn(`[${correlationId}] Rate limited (429), retrying in ${delayMs}ms (attempt ${attempt + 1}/${maxRetries})`);
            
            await delay(delayMs);
            continue;
          } else {
            // Task 3: Log max retries exceeded for 429
            console.error(`[${correlationId}] Max retry attempts exceeded (${maxRetries + 1} attempts) - Rate limited`);
          }
        }

        if (response.status === 401) {
          // Task 3: Log 401 unauthorized
          console.error(`[${correlationId}] Unauthorized (401), clearing tokens`);
          
          try {
            await tokenManager.handle401Response();
          } catch (tokenError) {
            console.warn(`[${correlationId}] TokenManager not available for 401 handling`);
          }
          
          return { data: null, error: { status: 401, code: 'UNAUTHORIZED', message: 'Authentication required. Please log in.', correlationId: serverCorrelationId }, correlationId: serverCorrelationId };
        }

        if (!response.ok) {
          const errorData = await parseJsonSafe(response);
          const errorMessage = (errorData as any)?.message || response.statusText || 'Request failed';
          
          // Task 3: Log HTTP error
          console.error(`[${correlationId}] HTTP error ${response.status}: ${errorMessage}`);
          
          return { data: null, error: { status: response.status, code: (errorData as any)?.code || response.statusText, message: errorMessage, details: errorData, correlationId: serverCorrelationId }, correlationId: serverCorrelationId };
        }

        const parsed = await parseJsonSafe(response);
        const hasDataErrorStructure = parsed && typeof parsed === 'object' && 'data' in parsed;
        
        return {
          data: hasDataErrorStructure ? (parsed as any).data : (parsed as TRes),
          error: hasDataErrorStructure ? (parsed as any).error : null,
          correlationId: serverCorrelationId,
        };
      } catch (error) {
        if (attempt === maxRetries) {
          const errorMessage = error instanceof Error ? error.message : 'Network request failed';
          
          // Task 3: Log max retries exceeded and network error
          console.error(`[${correlationId}] Max retry attempts exceeded (${maxRetries + 1} attempts) - Network error: ${errorMessage}`);
          
          return { data: null, error: { status: 0, code: 'NETWORK_ERROR', message: errorMessage, details: error, correlationId }, correlationId };
        }
        
        // Log retry attempt for network errors
        console.warn(`[${correlationId}] Network error on attempt ${attempt + 1}, retrying...`);
      }
    }

    // Task 3: Log max retries exceeded
    console.error(`[${correlationId}] Max retry attempts exceeded (${maxRetries + 1} attempts)`);
    
    return { data: null, error: { status: 0, code: 'MAX_RETRIES_EXCEEDED', message: 'Maximum retry attempts exceeded', correlationId }, correlationId };
  }, [baseUrl, maxRetries, legacyDelays, useExponentialBackoff, baseDelayMs, maxDelayMs, requestInterceptors, responseInterceptors]);

  return useMemo(() => ({
    request,
    get: <T>(url: string, opts?: { headers?: Record<string, string>; signal?: AbortSignal }) => request<undefined, T>('GET', url, opts),
    post: <TReq, TRes>(url: string, body?: TReq, opts?: { headers?: Record<string, string>; signal?: AbortSignal }) => request<TReq, TRes>('POST', url, { ...opts, body }),
    put: <TReq, TRes>(url: string, body?: TReq, opts?: { headers?: Record<string, string>; signal?: AbortSignal }) => request<TReq, TRes>('PUT', url, { ...opts, body }),
    patch: <TReq, TRes>(url: string, body?: TReq, opts?: { headers?: Record<string, string>; signal?: AbortSignal }) => request<TReq, TRes>('PATCH', url, { ...opts, body }),
    delete: <TRes>(url: string, opts?: { headers?: Record<string, string>; signal?: AbortSignal }) => request<undefined, TRes>('DELETE', url, opts),
  }), [request]);
}
