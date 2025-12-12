/**
 * PayPal Webhook Service
 * Client for PayPal payment and checkout webhooks
 * B0.2: Uses VITE_WEBHOOK_PAYPAL_URL (http://localhost:4023)
 */

import { createHttpClient } from '../httpClient';
import type { components } from '@/types/api/webhooks-paypal';

export type PayPalWebhookEvent = components['schemas']['PayPalWebhookEvent'];
export type PayPalPaymentCapture = components['schemas']['PayPalPaymentCapture'];
export type PayPalCheckoutOrder = components['schemas']['PayPalCheckoutOrder'];
export type SuccessResponse = components['schemas']['SuccessResponse'];

const WEBHOOK_PAYPAL_URL = import.meta.env.VITE_WEBHOOK_PAYPAL_URL as string;

if (!WEBHOOK_PAYPAL_URL) {
  console.warn('[PayPalWebhookService] VITE_WEBHOOK_PAYPAL_URL is not set. Service may not function correctly.');
}

const client = createHttpClient(WEBHOOK_PAYPAL_URL || '');

export const PayPalWebhookService = {
  async processPaymentCaptureCompleted(event: PayPalWebhookEvent, headers: {
    transmissionId: string;
    transmissionSig: string;
    certUrl: string;
  }): Promise<SuccessResponse> {
    const response = await client.post<SuccessResponse>(
      '/webhooks/paypal/PAYMENT.CAPTURE.COMPLETED',
      event,
      {
        headers: {
          'PAYPAL-TRANSMISSION-ID': headers.transmissionId,
          'PAYPAL-TRANSMISSION-SIG': headers.transmissionSig,
          'PAYPAL-CERT-URL': headers.certUrl,
        },
      }
    );
    return response.data;
  },

  async processCheckoutOrderApproved(event: PayPalWebhookEvent, headers: {
    transmissionId: string;
    transmissionSig: string;
    certUrl: string;
  }): Promise<SuccessResponse> {
    const response = await client.post<SuccessResponse>(
      '/webhooks/paypal/CHECKOUT.ORDER.APPROVED',
      event,
      {
        headers: {
          'PAYPAL-TRANSMISSION-ID': headers.transmissionId,
          'PAYPAL-TRANSMISSION-SIG': headers.transmissionSig,
          'PAYPAL-CERT-URL': headers.certUrl,
        },
      }
    );
    return response.data;
  },
};

export default PayPalWebhookService;
