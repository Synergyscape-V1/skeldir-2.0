/**
 * Attribution Service Client
 * Type-safe client for attribution endpoints (B0.2)
 * Port 4011
 */

import { attributionClient, type ApiResponse } from '@/lib/api-client-base';
import type { paths } from '@/types/api/attribution';

type RevenueRealtimeResponse = paths['/api/attribution/revenue/realtime']['get']['responses']['200']['content']['application/json'];

export class AttributionService {
  /**
   * Get realtime revenue data
   * GET /api/attribution/revenue/realtime
   */
  async getRealtimeRevenue(params?: {
    start_date?: string;
    end_date?: string;
  }): Promise<ApiResponse<RevenueRealtimeResponse>> {
    return attributionClient.get<RevenueRealtimeResponse>(
      '/api/attribution/revenue/realtime',
      { params }
    );
  }
}

export const attributionService = new AttributionService();
