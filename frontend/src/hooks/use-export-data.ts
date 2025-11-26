/**
 * Export Data Hook - Mockoon Integration
 * Handles data export requests to Export API (Port 4013)
 * Contract: export.yaml - POST /api/export/{format}
 */

import { useMutation } from '@tanstack/react-query';
import { 
  exportClient, 
  type ExportRequest, 
  type ExportDataResponse, 
  type ExportJobStatus 
} from '@/api/export-client';

export interface UseExportDataReturn {
  exportJSON: (request?: ExportRequest) => Promise<ExportDataResponse | null>;
  exportCSV: (request?: ExportRequest) => Promise<ExportJobStatus | null>;
  exportExcel: (request?: ExportRequest) => Promise<ExportJobStatus | null>;
  isExporting: boolean;
  error: Error | null;
}

/**
 * Export data in various formats from Mockoon Export API
 * Supports JSON (sync), CSV (async), and Excel (async) formats
 */
export function useExportData(): UseExportDataReturn {
  const jsonMutation = useMutation({
    mutationFn: async (request: ExportRequest = {}) => {
      const response = await exportClient.exportJSON(request);
      
      if (response.error) {
        throw new Error(response.error.detail || 'Failed to export JSON data');
      }

      return response.data;
    },
  });

  const csvMutation = useMutation({
    mutationFn: async (request: ExportRequest = {}) => {
      const response = await exportClient.exportCSV(request);
      
      if (response.error) {
        throw new Error(response.error.detail || 'Failed to export CSV data');
      }

      return response.data;
    },
  });

  const excelMutation = useMutation({
    mutationFn: async (request: ExportRequest = {}) => {
      const response = await exportClient.exportExcel(request);
      
      if (response.error) {
        throw new Error(response.error.detail || 'Failed to export Excel data');
      }

      return response.data;
    },
  });

  return {
    exportJSON: jsonMutation.mutateAsync,
    exportCSV: csvMutation.mutateAsync,
    exportExcel: excelMutation.mutateAsync,
    isExporting: jsonMutation.isPending || csvMutation.isPending || excelMutation.isPending,
    error: (jsonMutation.error || csvMutation.error || excelMutation.error) as Error | null,
  };
}
