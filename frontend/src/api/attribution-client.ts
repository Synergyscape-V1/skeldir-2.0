/**
 * Attribution Client Compatibility Layer
 * Provides backward-compatible attribution client interface
 */

import { attributionService } from './services/attribution-client';
import { ApiError } from '@/lib/rfc7807-handler';
import type { RealtimeRevenueCounter } from '@/api/generated/models/RealtimeRevenueCounter';

// Re-export types for convenience
export type { paths } from '@/types/api/attribution';

// Specific response types used by components - properly typed from generated SDK
export type RevenueRealtimeResponse = RealtimeRevenueCounter;
export type RevenueRealtimeResponseB2_6 = RealtimeRevenueCounter;

/**
 * Legacy-compatible attribution client
 * Wraps the new attributionService to maintain backward compatibility
 * B0.2: Only realtime revenue endpoint is supported per attribution.yaml contract
 */
export const attributionClient = {
  async getRealtimeRevenue(params?: { start_date?: string; end_date?: string }) {
    try {
      const response = await attributionService.getRealtimeRevenue(params);
      return {
        data: response.data,
        error: null,
        correlationId: response.correlationId,
      };
    } catch (error) {
      if (error instanceof ApiError) {
        return {
          data: null,
          error: {
            detail: error.getUserMessage(),
            status: error.problem.status,
          },
          correlationId: error.correlationId,
        };
      }

      return {
        data: null,
        error: {
          detail: error instanceof Error ? error.message : 'Failed to fetch revenue data',
          status: 500,
        },
        correlationId: undefined,
      };
    }
  },
};

// Also export the new service for direct use
export { attributionService };
