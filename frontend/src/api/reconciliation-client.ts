/**
 * Reconciliation Client Compatibility Layer
 */

import { reconciliationService } from './services/reconciliation-client';
import { ApiError } from '@/lib/rfc7807-handler';

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
