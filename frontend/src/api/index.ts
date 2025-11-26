/**
 * API Client Barrel Exports
 * Central export point for all API services
 */

// Export all service clients
export * from './services';

// Export error handling utilities
export { ApiError, type ProblemDetails } from '@/lib/rfc7807-handler';
