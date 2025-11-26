import { useState, useCallback } from 'react';

/**
 * useEtagCache - Reusable hook for HTTP ETag caching
 * 
 * Implements HTTP ETag conditional request pattern per Frontend Architecture Guide
 * Section 4.5: "ETag Handling - 304 Response Optimization"
 * 
 * @example
 * const { etag, getHeaders, handleResponse } = useEtagCache();
 * 
 * // Add If-None-Match header to requests
 * const headers = { ...baseHeaders, ...getHeaders() };
 * 
 * // Handle response and check if data changed
 * const dataChanged = handleResponse(response);
 * if (dataChanged) {
 *   // Update UI with new data
 * } else {
 *   // 304 Not Modified - reuse cached data
 * }
 */
export function useEtagCache() {
  const [etag, setEtag] = useState<string | null>(null);

  /**
   * Returns If-None-Match header object if ETag exists
   * Empty object if no ETag cached yet
   */
  const getHeaders = useCallback((): Record<string, string> => {
    if (!etag) {
      return {};
    }
    return {
      'If-None-Match': etag,
    };
  }, [etag]);

  /**
   * Extracts ETag from response and returns whether data changed
   * 
   * IMPORTANT: Only caches ETags from successful 2xx responses to prevent
   * pinning failure ETags from error responses.
   * 
   * @param response - Fetch Response object or HTTP status code
   * @param newEtag - Optional: ETag value extracted from response headers
   * @returns true if data changed (200 OK), false if not modified (304)
   */
  const handleResponse = useCallback((
    response: Response | number,
    newEtag?: string
  ): boolean => {
    // Handle Response object
    if (typeof response === 'object' && 'status' in response) {
      const status = response.status;
      
      // 304 Not Modified - no data change
      if (status === 304) {
        return false;
      }
      
      // Only cache ETags from successful 2xx responses
      // This prevents pinning an ETag from an error response (4xx, 5xx)
      if (status >= 200 && status < 300) {
        // Extract ETag from response headers (case-insensitive)
        const responseEtag = response.headers.get('ETag') || response.headers.get('etag');
        
        // Store new ETag if different from current
        if (responseEtag && responseEtag !== etag) {
          setEtag(responseEtag);
        }
      }
      
      // Data changed if status is 200 OK
      return status === 200;
    }
    
    // Handle status code number
    const status = response as number;
    
    // 304 Not Modified - no data change
    if (status === 304) {
      return false;
    }
    
    // Only cache ETags from successful 2xx responses
    if (status >= 200 && status < 300 && newEtag && newEtag !== etag) {
      setEtag(newEtag);
    }
    
    // Data changed if status is 200 OK
    return status === 200;
  }, [etag]);

  /**
   * Manually clear cached ETag (e.g., on logout or cache invalidation)
   */
  const clearEtag = useCallback(() => {
    setEtag(null);
  }, []);

  /**
   * Manually set ETag (e.g., when receiving ETag through different channel)
   */
  const updateEtag = useCallback((newEtag: string | null) => {
    setEtag(newEtag);
  }, []);

  return {
    etag,
    getHeaders,
    handleResponse,
    clearEtag,
    setEtag: updateEtag,
  };
}

/**
 * Type definitions for useEtagCache return value
 */
export type EtagCache = ReturnType<typeof useEtagCache>;
