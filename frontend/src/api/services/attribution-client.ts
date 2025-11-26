/**
 * Attribution Service Client
 * Type-safe client for attribution endpoints
 */

import { attributionClient, type ApiResponse } from '@/lib/api-client-base';
import type { paths } from '@/types/api/attribution';

type RevenueRealtimeResponse = paths['/api/attribution/revenue/realtime']['get']['responses']['200']['content']['application/json'];
type ChannelsResponse = paths['/api/attribution/channels']['get']['responses']['200']['content']['application/json'];
type ModelsCompareResponse = paths['/api/attribution/models/compare']['get']['responses']['200']['content']['application/json'];

export class AttributionService {
  /**
   * Get realtime revenue data
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

  /**
   * Get channel performance data
   */
  async getChannels(params?: {
    start_date?: string;
    end_date?: string;
  }): Promise<ApiResponse<ChannelsResponse>> {
    return attributionClient.get<ChannelsResponse>(
      '/api/attribution/channels',
      { params }
    );
  }

  /**
   * Compare attribution models
   */
  async compareModels(params?: {
    start_date?: string;
    end_date?: string;
  }): Promise<ApiResponse<ModelsCompareResponse>> {
    return attributionClient.get<ModelsCompareResponse>(
      '/api/attribution/models/compare',
      { params }
    );
  }
}

export const attributionService = new AttributionService();
