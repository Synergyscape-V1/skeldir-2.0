/**
 * HTTP Client Factory
 * Creates configured API clients for different services
 * B0.2: Uses ApiClient from api-client-base.ts with per-service base URLs
 */

import { ApiClient, ApiResponse } from '@/lib/api-client-base';

/**
 * Factory function to create a configured HTTP client for a specific base URL
 * @param baseUrl - The base URL for the API service
 * @returns ApiClient instance configured with the base URL
 */
export function createHttpClient(baseUrl: string): ApiClient {
  if (!baseUrl) {
    console.warn('[HTTP Client] Warning: baseUrl is empty. Requests may fail.');
  }
  return new ApiClient(baseUrl);
}

/**
 * Re-export types for convenience
 */
export type { ApiResponse };
export { ApiClient };
