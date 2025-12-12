/**
 * Stripe Webhook Service
 * Client for Stripe payment and checkout webhooks
 * B0.2: Uses VITE_WEBHOOK_STRIPE_URL (http://localhost:4021)
 */

import { createHttpClient } from '../httpClient';
import type { components } from '@/types/api/webhooks-stripe';

export type StripeEvent = components['schemas']['StripeEvent'];
export type StripePaymentIntent = components['schemas']['StripePaymentIntent'];
export type StripeCheckoutSession = components['schemas']['StripeCheckoutSession'];
export type SuccessResponse = components['schemas']['SuccessResponse'];

const WEBHOOK_STRIPE_URL = import.meta.env.VITE_WEBHOOK_STRIPE_URL as string;

if (!WEBHOOK_STRIPE_URL) {
  console.warn('[StripeWebhookService] VITE_WEBHOOK_STRIPE_URL is not set. Service may not function correctly.');
}

const client = createHttpClient(WEBHOOK_STRIPE_URL || '');

export const StripeWebhookService = {
  async processPaymentIntentSucceeded(event: StripeEvent, signature: string): Promise<SuccessResponse> {
    const response = await client.post<SuccessResponse>(
      '/webhooks/stripe/payment_intent.succeeded',
      event,
      {
        headers: {
          'Stripe-Signature': signature,
        },
      }
    );
    return response.data;
  },

  async processCheckoutSessionCompleted(event: StripeEvent, signature: string): Promise<SuccessResponse> {
    const response = await client.post<SuccessResponse>(
      '/webhooks/stripe/checkout.session.completed',
      event,
      {
        headers: {
          'Stripe-Signature': signature,
        },
      }
    );
    return response.data;
  },
};

export default StripeWebhookService;
