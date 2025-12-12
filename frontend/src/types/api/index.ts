/**
 * B0.2 API Type Exports
 * Barrel file with namespaced exports to avoid type conflicts
 * 
 * Each contract exports: paths, webhooks, components, operations, $defs
 * Using namespace imports to prevent export name collisions
 */

import * as AuthTypes from './auth';
import * as AttributionTypes from './attribution';
import * as ReconciliationTypes from './reconciliation';
import * as ExportTypes from './export';
import * as HealthTypes from './health';
import * as ErrorTypes from './errors';
import * as LLMInvestigationsTypes from './llm-investigations';
import * as LLMBudgetTypes from './llm-budget';
import * as LLMExplanationsTypes from './llm-explanations';
import * as WebhooksShopifyTypes from './webhooks-shopify';
import * as WebhooksStripeTypes from './webhooks-stripe';
import * as WebhooksWooCommerceTypes from './webhooks-woocommerce';
import * as WebhooksPayPalTypes from './webhooks-paypal';

export {
  AuthTypes,
  AttributionTypes,
  ReconciliationTypes,
  ExportTypes,
  HealthTypes,
  ErrorTypes,
  LLMInvestigationsTypes,
  LLMBudgetTypes,
  LLMExplanationsTypes,
  WebhooksShopifyTypes,
  WebhooksStripeTypes,
  WebhooksWooCommerceTypes,
  WebhooksPayPalTypes,
};

export type { paths as AuthPaths, components as AuthComponents, operations as AuthOperations } from './auth';
export type { paths as AttributionPaths, components as AttributionComponents, operations as AttributionOperations } from './attribution';
export type { paths as ReconciliationPaths, components as ReconciliationComponents, operations as ReconciliationOperations } from './reconciliation';
export type { paths as ExportPaths, components as ExportComponents, operations as ExportOperations } from './export';
export type { paths as HealthPaths, components as HealthComponents, operations as HealthOperations } from './health';
