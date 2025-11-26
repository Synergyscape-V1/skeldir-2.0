/**
 * SDK Migration Example
 * Demonstrates how to migrate from useApiClient to SDK-based approach
 */

import { useEffect, useState } from 'react';
import { useApiClient } from '@/hooks/use-api-client';
import { useSDKClient } from '@/api/sdk-client';
import type { RealtimeRevenueCounter } from '@/api/generated/models/RealtimeRevenueCounter';

/**
 * BEFORE: Using useApiClient (manual API calls)
 */
export function RevenueCounter_OLD() {
  const [revenue, setRevenue] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const apiClient = useApiClient();

  useEffect(() => {
    const fetchRevenue = async () => {
      setLoading(true);
      
      // Manual API call with generic typing
      const response = await apiClient.get<{ 
        total_revenue?: number;
        verified?: boolean;
      }>('/api/attribution/revenue');

      if (response.data) {
        // Fields might not exist, no autocomplete
        setRevenue(response.data.total_revenue || 0);
      }
      
      setLoading(false);
    };

    fetchRevenue();
  }, [apiClient]);

  if (loading) return <div>Loading...</div>;
  
  return (
    <div>
      <h2>Revenue (OLD)</h2>
      <p>${revenue.toLocaleString()}</p>
    </div>
  );
}

/**
 * AFTER: Using SDK Client (contract-driven, type-safe)
 */
export function RevenueCounter_NEW() {
  const [revenue, setRevenue] = useState<RealtimeRevenueCounter | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const sdk = useSDKClient();

  useEffect(() => {
    const fetchRevenue = async () => {
      setLoading(true);
      setError(null);
      
      // Generate correlation ID for request tracking
      const correlationId = crypto.randomUUID();
      
      // SDK call with full type safety
      const { data, error: apiError } = await sdk.getRealtimeRevenue(correlationId);

      if (apiError) {
        setError(`[${apiError.correlationId}] ${apiError.message}`);
        setLoading(false);
        return;
      }

      if (data) {
        // Full autocomplete for all contract fields
        setRevenue(data);
        console.log(`[${correlationId}] Revenue updated:`, {
          total: data.total_revenue,
          events: data.event_count,
          freshness: data.data_freshness_seconds,
          verified: data.verified
        });
      }
      
      setLoading(false);
    };

    fetchRevenue();
  }, [sdk]);

  if (loading) return <div>Loading...</div>;
  if (error) return <div className="text-destructive">{error}</div>;
  if (!revenue) return <div>No data</div>;
  
  return (
    <div className="space-y-2">
      <h2>Revenue (NEW - SDK)</h2>
      <p className="text-3xl font-bold">
        ${revenue.total_revenue.toLocaleString()}
      </p>
      <div className="text-sm text-muted-foreground space-y-1">
        <p>Events: {revenue.event_count.toLocaleString()}</p>
        <p>Last Updated: {new Date(revenue.last_updated).toLocaleString()}</p>
        <p>Freshness: {revenue.data_freshness_seconds}s ago</p>
        <p>Verified: {revenue.verified ? '✓' : '✗'}</p>
        {revenue.upgrade_notice && (
          <p className="text-primary">{revenue.upgrade_notice}</p>
        )}
      </div>
    </div>
  );
}

/**
 * Advanced: Using SDK with ETag caching
 */
export function RevenueCounter_WITH_CACHE() {
  const [revenue, setRevenue] = useState<RealtimeRevenueCounter | null>(null);
  const [etag, setETag] = useState<string | undefined>();
  const [cacheHit, setCacheHit] = useState(false);
  const sdk = useSDKClient();

  useEffect(() => {
    const fetchRevenue = async () => {
      const correlationId = crypto.randomUUID();
      
      try {
        // Pass ETag from previous response
        const { data, error } = await sdk.getRealtimeRevenue(correlationId, etag);

        if (error) {
          if (error.status === 304) {
            // 304 Not Modified - use cached data
            setCacheHit(true);
            console.log(`[${correlationId}] Cache hit - data unchanged`);
            return;
          }
          throw new Error(error.message);
        }

        if (data) {
          setRevenue(data);
          setCacheHit(false);
          
          // Store ETag for next request
          // Note: In real implementation, extract from response headers
          setETag('new-etag-value'); // Placeholder
        }
      } catch (err) {
        console.error('Revenue fetch failed:', err);
      }
    };

    const interval = setInterval(fetchRevenue, 30000); // Poll every 30s
    fetchRevenue(); // Initial fetch

    return () => clearInterval(interval);
  }, [sdk, etag]);

  if (!revenue) return <div>Loading...</div>;
  
  return (
    <div>
      <h2>Revenue (With Cache)</h2>
      <p>${revenue.total_revenue.toLocaleString()}</p>
      {cacheHit && (
        <p className="text-xs text-muted-foreground">
          ⚡ Using cached data (304 Not Modified)
        </p>
      )}
    </div>
  );
}

/**
 * Benefits of SDK Approach:
 * 
 * 1. Type Safety
 *    - Full TypeScript types from OpenAPI contracts
 *    - Autocomplete for all fields
 *    - Compile-time error checking
 * 
 * 2. Contract Compliance
 *    - Guaranteed to match backend API structure
 *    - Automatic updates when contracts change
 *    - No manual type definitions needed
 * 
 * 3. Developer Experience
 *    - IntelliSense shows all available fields
 *    - JSDoc comments from contract descriptions
 *    - Import types directly from generated models
 * 
 * 4. Maintainability
 *    - Single source of truth (OpenAPI contract)
 *    - Regenerate SDK when contract updates
 *    - Less manual API client code to maintain
 * 
 * 5. Error Handling
 *    - Typed error responses
 *    - Correlation ID tracking built-in
 *    - Consistent error format across all endpoints
 */
