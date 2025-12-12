/**
 * Reconciliation Client Compatibility Layer (B0.2)
 * Port 4014
 */

import { reconciliationService } from './services/reconciliation-client';
import { ApiError } from '@/lib/rfc7807-handler';
import type { paths } from '@/types/api/reconciliation';

export type ReconciliationStatus = paths['/api/reconciliation/status']['get']['responses']['200']['content']['application/json'];

export const reconciliationClient = {
  async getStatus() {
    try {
      const response = await reconciliationService.getStatus();
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
          },
          correlationId: error.correlationId,
        };
      }

      return {
        data: null,
        error: {
          detail: 'Failed to fetch reconciliation status',
        },
        correlationId: undefined,
      };
    }
  },
};

export { reconciliationService };
