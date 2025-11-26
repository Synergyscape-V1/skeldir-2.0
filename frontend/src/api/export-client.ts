/**
 * Export Client Compatibility Layer
 * Maintains exact original method names: exportJSON, exportCSV, exportExcel
 */

import { exportService } from './services/export-client';
import { ApiError } from '@/lib/rfc7807-handler';

export const exportClient = {
  // Original capitalized method names for backward compatibility
  async exportJSON(request?: { data_type?: string; filters?: any }) {
    try {
      const response = await exportService.exportJson(request || { data_type: 'attribution' });
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
          detail: 'Export failed',
        },
        correlationId: undefined,
      };
    }
  },

  async exportCSV(request?: { data_type?: string; filters?: any }) {
    try {
      const response = await exportService.exportCsv(request || { data_type: 'attribution' });
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
          detail: 'Export failed',
        },
        correlationId: undefined,
      };
    }
  },

  async exportExcel(request?: { data_type?: string; filters?: any }) {
    // Excel export uses CSV export as base (can be enhanced later)
    try {
      const response = await exportService.exportCsv(request || { data_type: 'attribution' });
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
          detail: 'Export failed',
        },
        correlationId: undefined,
      };
    }
  },
};

export { exportService };
