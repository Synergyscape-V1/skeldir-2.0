/**
 * Health Monitoring API Client
 * Contract: health.yaml (Port 4016 - B0.2)
 * Endpoints: /api/health, /api/health/services
 */

import { healthClient as baseHealthClient, type ApiResponse } from '@/lib/api-client-base';

export interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  timestamp: string;
  version: string;
  uptime_seconds: number;
  services: Record<string, ServiceHealth>;
}

export interface ServiceHealth {
  status: 'healthy' | 'degraded' | 'unhealthy';
  response_time_ms: number;
  last_check: string;
  error_message?: string;
}

export interface ServiceHealthDetail {
  service_name: string;
  status: 'healthy' | 'degraded' | 'unhealthy';
  response_time_ms: number;
  checks: HealthCheck[];
  dependencies: DependencyHealth[];
}

export interface HealthCheck {
  check_name: string;
  status: 'pass' | 'fail';
  message?: string;
  timestamp: string;
}

export interface DependencyHealth {
  dependency_name: string;
  status: 'available' | 'unavailable';
  latency_ms: number;
}

/**
 * Health Service - Handles system health monitoring
 */
export class HealthService {
  /**
   * GET /api/health
   * Get overall system health status
   */
  async getSystemHealth(): Promise<ApiResponse<HealthStatus>> {
    return baseHealthClient.get<HealthStatus>('/api/health');
  }

  /**
   * GET /api/health/services/{serviceName}
   * Get detailed health information for a specific service
   */
  async getServiceHealth(serviceName: string): Promise<ApiResponse<ServiceHealthDetail>> {
    return baseHealthClient.get<ServiceHealthDetail>(`/api/health/services/${serviceName}`);
  }
}

export const healthService = new HealthService();
export const healthClient = healthService;
