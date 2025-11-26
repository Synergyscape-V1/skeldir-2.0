/**
 * Service Client Exports
 * Barrel file for all API service clients
 */

export { authService, AuthService } from './auth-client';
export { attributionService, AttributionService } from './attribution-client';
export { reconciliationService, ReconciliationService } from './reconciliation-client';
export { exportService, ExportService } from './export-client';
export { healthService, HealthService } from './health-client';

// Re-export error types for convenience
export { ApiError, type ProblemDetails } from '@/lib/rfc7807-handler';
