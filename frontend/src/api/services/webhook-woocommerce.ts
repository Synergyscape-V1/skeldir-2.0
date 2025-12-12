/**
 * WooCommerce Webhook Service
 * Client for WooCommerce order webhooks
 * B0.2: Uses VITE_WEBHOOK_WOOCOMMERCE_URL (http://localhost:4022)
 */

import { createHttpClient } from '../httpClient';
import type { components } from '@/types/api/webhooks-woocommerce';

export type WooOrder = components['schemas']['WooOrder'];
export type SuccessResponse = components['schemas']['SuccessResponse'];

const WEBHOOK_WOOCOMMERCE_URL = import.meta.env.VITE_WEBHOOK_WOOCOMMERCE_URL as string;

if (!WEBHOOK_WOOCOMMERCE_URL) {
  console.warn('[WooCommerceWebhookService] VITE_WEBHOOK_WOOCOMMERCE_URL is not set. Service may not function correctly.');
}

const client = createHttpClient(WEBHOOK_WOOCOMMERCE_URL || '');

export const WooCommerceWebhookService = {
  async processOrderCreated(order: WooOrder, headers: {
    signature: string;
    source: string;
  }): Promise<SuccessResponse> {
    const response = await client.post<SuccessResponse>(
      '/webhooks/woocommerce/order.created',
      order,
      {
        headers: {
          'X-WC-Webhook-Signature': headers.signature,
          'X-WC-Webhook-Topic': 'order.created',
          'X-WC-Webhook-Source': headers.source,
        },
      }
    );
    return response.data;
  },

  async processOrderUpdated(order: WooOrder, headers: {
    signature: string;
    source: string;
  }): Promise<SuccessResponse> {
    const response = await client.post<SuccessResponse>(
      '/webhooks/woocommerce/order.updated',
      order,
      {
        headers: {
          'X-WC-Webhook-Signature': headers.signature,
          'X-WC-Webhook-Topic': 'order.updated',
          'X-WC-Webhook-Source': headers.source,
        },
      }
    );
    return response.data;
  },
};

export default WooCommerceWebhookService;
