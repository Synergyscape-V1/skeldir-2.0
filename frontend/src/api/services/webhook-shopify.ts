/**
 * Shopify Webhook Service
 * Client for Shopify order and checkout webhooks
 * B0.2: Uses VITE_WEBHOOK_SHOPIFY_URL (http://localhost:4020)
 */

import { createHttpClient } from '../httpClient';
import type { components } from '@/types/api/webhooks-shopify';

export type ShopifyOrder = components['schemas']['ShopifyOrder'];
export type ShopifyCheckout = components['schemas']['ShopifyCheckout'];
export type SuccessResponse = components['schemas']['SuccessResponse'];

const WEBHOOK_SHOPIFY_URL = import.meta.env.VITE_WEBHOOK_SHOPIFY_URL as string;

if (!WEBHOOK_SHOPIFY_URL) {
  console.warn('[ShopifyWebhookService] VITE_WEBHOOK_SHOPIFY_URL is not set. Service may not function correctly.');
}

const client = createHttpClient(WEBHOOK_SHOPIFY_URL || '');

export const ShopifyWebhookService = {
  async processOrderCreated(order: ShopifyOrder, headers: {
    hmacSha256: string;
    shopDomain: string;
  }): Promise<SuccessResponse> {
    const response = await client.post<SuccessResponse>(
      '/webhooks/shopify/orders/create',
      order,
      {
        headers: {
          'X-Shopify-Hmac-SHA256': headers.hmacSha256,
          'X-Shopify-Shop-Domain': headers.shopDomain,
          'X-Shopify-Topic': 'orders/create',
        },
      }
    );
    return response.data;
  },

  async processCheckoutUpdated(checkout: ShopifyCheckout, headers: {
    hmacSha256: string;
    shopDomain: string;
  }): Promise<SuccessResponse> {
    const response = await client.post<SuccessResponse>(
      '/webhooks/shopify/checkouts/update',
      checkout,
      {
        headers: {
          'X-Shopify-Hmac-SHA256': headers.hmacSha256,
          'X-Shopify-Shop-Domain': headers.shopDomain,
          'X-Shopify-Topic': 'checkouts/update',
        },
      }
    );
    return response.data;
  },
};

export default ShopifyWebhookService;
