/**
 * Export Service Client
 * Type-safe client for export endpoints
 */

import { exportClient, type ApiResponse } from '@/lib/api-client-base';
import type { paths } from '@/types/api/export';

type ExportJsonRequest = paths['/api/export/json']['post']['requestBody']['content']['application/json'];
type ExportJsonResponse = paths['/api/export/json']['post']['responses']['200']['content']['application/json'];
type ExportCsvRequest = paths['/api/export/csv']['post']['requestBody']['content']['application/json'];
type ExportCsvResponse = paths['/api/export/csv']['post']['responses']['200']['content']['application/json'];

export class ExportService {
  /**
   * Export data as JSON
   */
  async exportJson(request: ExportJsonRequest): Promise<ApiResponse<ExportJsonResponse>> {
    return exportClient.post<ExportJsonResponse>('/api/export/json', request);
  }

  /**
   * Export data as CSV
   */
  async exportCsv(request: ExportCsvRequest): Promise<ApiResponse<ExportCsvResponse>> {
    return exportClient.post<ExportCsvResponse>('/api/export/csv', request);
  }
}

export const exportService = new ExportService();
