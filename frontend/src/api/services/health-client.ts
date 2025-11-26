/**
 * Health Monitoring Service Client
 * Type-safe client for health endpoints
 */

import { healthClient, type ApiResponse } from '@/lib/api-client-base';
import type { paths } from '@/types/api/health';

type HealthResponse = paths['/api/health']['get']['responses']['200']['content']['application/json'];

export class HealthService {
  /**
   * Get system health status
   */
  async getHealth(): Promise<ApiResponse<HealthResponse>> {
    return healthClient.get<HealthResponse>('/api/health');
  }
}

export const healthService = new HealthService();
