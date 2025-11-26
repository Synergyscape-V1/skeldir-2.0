/**
 * SDK Client Integration Layer
 * Wraps auto-generated TypeScript SDK with app-specific patterns
 */

import { SkelAttributionClient } from './generated/SkelAttributionClient';
import type { OpenAPIConfig } from './generated/core/OpenAPI';
import { tokenManager } from '@/lib/token-manager';

export class SDKClient {
  private client: SkelAttributionClient;
  private baseUrl: string;

  constructor(baseUrl?: string) {
    this.baseUrl = baseUrl || import.meta.env.VITE_MOCK_ATTRIBUTION_URL || 'http://localhost:4010';
    this.client = this.createClient();
  }

  private createClient(): SkelAttributionClient {
    const config: Partial<OpenAPIConfig> = {
      BASE: this.baseUrl,
      WITH_CREDENTIALS: true,
      CREDENTIALS: 'include',
      // Token will be added dynamically per request
      TOKEN: undefined,
    };

    return new SkelAttributionClient(config);
  }

  /**
   * Get JWT token from token manager for authentication
   */
  private async getAuthToken(): Promise<string | undefined> {
    try {
      const authHeader = await tokenManager.getAuthHeader();
      // Extract token from "Bearer <token>" format
      if (authHeader.Authorization) {
        return authHeader.Authorization.replace('Bearer ', '');
      }
    } catch (error) {
      console.warn('TokenManager not initialized, proceeding without auth');
    }
    return undefined;
  }

  /**
   * Attribution Service - Realtime Revenue Counter
   */
  async getRealtimeRevenue(correlationId: string, etag?: string) {
    const token = await this.getAuthToken();
    
    // Update client token
    this.client.request.config.TOKEN = token;
    
    try {
      const result = await this.client.attribution.getRealtimeRevenue(
        correlationId,
        etag
      );
      
      return { data: result, error: null };
    } catch (error: any) {
      // Handle SDK errors
      return {
        data: null,
        error: {
          status: error.status || 0,
          message: error.message || 'Request failed',
          correlationId,
          details: error.body
        }
      };
    }
  }

  /**
   * Placeholder methods for other services (awaiting contracts)
   * These will be implemented when additional OpenAPI contracts are available
   */

  // Auth Service (awaiting auth.yaml)
  async verifyToken() {
    throw new Error('Auth service not yet available - awaiting auth.yaml contract');
  }

  async refreshToken() {
    throw new Error('Auth service not yet available - awaiting auth.yaml contract');
  }

  // Export Service (awaiting export.yaml)
  async exportCSV() {
    throw new Error('Export service not yet available - awaiting export.yaml contract');
  }

  // Reconciliation Service (awaiting reconciliation.yaml)
  async getReconciliationStatus() {
    throw new Error('Reconciliation service not yet available - awaiting reconciliation.yaml contract');
  }

  // Error Logging Service (awaiting errors.yaml)
  async logError() {
    throw new Error('Error logging service not yet available - awaiting errors.yaml contract');
  }
}

/**
 * Singleton SDK client instance
 */
export const sdkClient = new SDKClient();

/**
 * Hook for React components to use SDK client
 */
export function useSDKClient() {
  return sdkClient;
}
