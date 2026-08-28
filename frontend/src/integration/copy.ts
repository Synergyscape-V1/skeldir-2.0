import type { ClaimProvider, CommerceProvider, IntegrationProvider, IntegrationStatus } from './types';

export const INTEGRATION_COPY = {
  commerceGroupTitle: 'Commerce truth',
  commerceGroupDescription:
    'Commerce and payment systems are the authority source for verified revenue.',
  claimGroupTitle: 'Claim sources',
  claimGroupDescription:
    'Ad platforms provide claims. Skeldir reconciles those claims against commerce evidence.',

  commerceAuthorityCopy: 'Authority source for verified revenue.',
  claimSourceCopy: 'Claims are reconciled against commerce truth.',

  connect: 'Connect',
  connecting: 'Connecting…',
  repair: 'Repair connection',
  repairing: 'Repairing…',

  lastEvent: 'Last event',
  lastClaim: 'Last claim received',
  verificationStatus: 'Verification status',
  reconciliationReadiness: 'Reconciliation readiness',
  connectionStatus: 'Connection status',

  lastEventUnavailable: 'Last event unavailable',
  lastClaimUnavailable: 'Last claim unavailable',

  unknownStatusError: 'Unknown integration status returned. Contact support if this persists.',
  invalidProviderError: 'Unknown integration provider.',

  providerLabels: {
    shopify: 'Shopify',
    woocommerce: 'WooCommerce',
    stripe: 'Stripe',
    paypal: 'PayPal',
    meta_ads: 'Meta Ads',
    google_ads: 'Google Ads',
    tiktok_ads: 'TikTok Ads',
    linkedin_ads: 'LinkedIn Ads',
    other: 'Other supported sources',
  } satisfies Record<IntegrationProvider, string>,

  statusLabels: {
    not_connected: 'Not connected',
    connecting: 'Connecting',
    connected: 'Connected',
    connection_failed: 'Connection failed',
    verification_pending: 'Verification pending',
    verification_ready: 'Verification ready',
    verification_failed: 'Verification failed',
    last_event_unavailable: 'Last event unavailable',
    last_claim_unavailable: 'Last claim unavailable',
    repair_required: 'Repair required',
    repair_pending: 'Repair in progress',
    permission_denied: 'Permission denied',
    rate_limited: 'Rate limited',
    network_error: 'Network error',
    unknown_status: 'Unknown status',
  } satisfies Record<IntegrationStatus, string>,

  actionFailed: 'Connection action failed. No financial truth was changed.',
  permissionDenied: 'You do not have permission to manage integrations for this workspace.',
  rateLimited: 'Too many connection attempts. Try again shortly.',
  networkError: 'Integration service unavailable. Try again shortly.',

  commerceReadySummary: 'At least one commerce truth source is connected.',
  commerceMissingSummary: 'Connect at least one commerce or payment source.',
  claimReadySummary: 'Claim source connected and reconciliation readiness tracked.',
  claimSkippedSummary: 'Claim sources skipped. Commerce truth verification remains active.',
} as const;

export function providerLabel(provider: IntegrationProvider): string {
  return INTEGRATION_COPY.providerLabels[provider];
}

export function statusLabel(status: IntegrationStatus): string {
  return INTEGRATION_COPY.statusLabels[status];
}

export function commerceProviderLabel(provider: CommerceProvider): string {
  return INTEGRATION_COPY.providerLabels[provider];
}

export function claimProviderLabel(provider: ClaimProvider): string {
  return INTEGRATION_COPY.providerLabels[provider];
}
