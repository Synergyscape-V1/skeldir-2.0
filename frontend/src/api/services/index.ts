/**
 * B0.2 Service Client Exports
 * Barrel file for all 12 API service clients
 */

export { authService, AuthService } from './auth-client';
export { attributionService, AttributionService } from './attribution-client';
export { reconciliationService, ReconciliationService } from './reconciliation-client';
export { exportService, ExportService } from './export-client';
export { healthService, HealthService } from './health-client';

export { ShopifyWebhookService } from './webhook-shopify';
export { StripeWebhookService } from './webhook-stripe';
export { WooCommerceWebhookService } from './webhook-woocommerce';
export { PayPalWebhookService } from './webhook-paypal';

export { LLMInvestigationsService } from './llm-investigations';
export { LLMBudgetService } from './llm-budget';
export { LLMExplanationsService } from './llm-explanations';

export { ApiError, type ProblemDetails } from '@/lib/rfc7807-handler';
