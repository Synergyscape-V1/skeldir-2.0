/**
 * Reconciliation Service Client
 * Type-safe client for reconciliation endpoints
 */

import { reconciliationClient, type ApiResponse } from '@/lib/api-client-base';
import type { paths } from '@/types/api/reconciliation';

type ReconciliationStatusResponse = paths['/api/reconciliation/status']['get']['responses']['200']['content']['application/json'];

export class ReconciliationService {
  /**
   * Get reconciliation status
   */
  async getStatus(): Promise<ApiResponse<ReconciliationStatusResponse>> {
    return reconciliationClient.get<ReconciliationStatusResponse>(
      '/api/reconciliation/status'
    );
  }
}

export const reconciliationService = new ReconciliationService();
