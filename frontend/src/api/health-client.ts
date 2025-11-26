/**
 * Health Monitoring API Client
 * Contract: health.yaml (Port 4014)
 * Endpoints: /api/health, /api/health/services
 */

import { BaseApiClient, type ApiResponse } from '@/lib/api-client-base';

// Overall System Health Response
export interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  timestamp: string; // ISO 8601
  version: string;
  uptime_seconds: number;
  services: Record<string, ServiceHealth>;
}

// Individual Service Health
export interface ServiceHealth {
  status: 'healthy' | 'degraded' | 'unhealthy';
  response_time_ms: number;
  last_check: string; // ISO 8601
  error_message?: string;
}

// Detailed Service Health Response
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
  timestamp: string; // ISO 8601
}

export interface DependencyHealth {
  dependency_name: string;
  status: 'available' | 'unavailable';
  latency_ms: number;
}

/**
 * HealthClient - Handles system health monitoring
 */
export class HealthClient extends BaseApiClient {
  constructor(baseUrl?: string) {
    super({
      baseUrl: baseUrl || import.meta.env.VITE_HEALTH_API_URL || 'http://localhost:4014',
      serviceName: 'HealthService',
    });
  }

  /**
   * GET /api/health
   * Get overall system health status
   */
  async getSystemHealth(): Promise<ApiResponse<HealthStatus>> {
    return this.get<HealthStatus>('/api/health');
  }

  /**
   * GET /api/health/services/{serviceName}
   * Get detailed health information for a specific service
   */
  async getServiceHealth(serviceName: string): Promise<ApiResponse<ServiceHealthDetail>> {
    return this.get<ServiceHealthDetail>(`/api/health/services/${serviceName}`);
  }
}

/**
 * Singleton instance of HealthClient
 */
export const healthClient = new HealthClient();
