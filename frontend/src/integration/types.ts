export type CommerceProvider = 'shopify' | 'woocommerce' | 'stripe' | 'paypal';

export type ClaimProvider = 'meta_ads' | 'google_ads' | 'tiktok_ads' | 'linkedin_ads' | 'other';

export type IntegrationProvider = CommerceProvider | ClaimProvider;

export type IntegrationKind = 'commerce' | 'claim';

export type IntegrationStatus =
  | 'not_connected'
  | 'connecting'
  | 'connected'
  | 'connection_failed'
  | 'verification_pending'
  | 'verification_ready'
  | 'verification_failed'
  | 'last_event_unavailable'
  | 'last_claim_unavailable'
  | 'repair_required'
  | 'repair_pending'
  | 'permission_denied'
  | 'rate_limited'
  | 'network_error'
  | 'unknown_status';

export interface IntegrationSourceState {
  provider: IntegrationProvider;
  kind: IntegrationKind;
  status: IntegrationStatus;
  lastEventAt?: string | null;
  lastClaimAt?: string | null;
  verificationLabel?: string;
  reconciliationLabel?: string;
  errorMessage?: string;
}

export interface WorkspaceActivationContext {
  tenantId: string;
  workspaceName: string;
  activationStatus: 'pending' | 'confirmed' | 'failed';
}

export type IntegrationOutcome =
  | { kind: 'workspace_ready'; workspace: WorkspaceActivationContext }
  | { kind: 'workspace_invalid'; detail?: string }
  | { kind: 'workspace_create_failed'; detail?: string }
  | { kind: 'commerce_connected'; provider: CommerceProvider; state: IntegrationSourceState }
  | { kind: 'commerce_connection_failed'; provider: CommerceProvider; detail?: string }
  | { kind: 'commerce_verification_pending'; provider: CommerceProvider; state: IntegrationSourceState }
  | { kind: 'commerce_verification_failed'; provider: CommerceProvider; detail?: string }
  | { kind: 'claim_source_connected'; provider: ClaimProvider; state: IntegrationSourceState }
  | { kind: 'claim_source_connection_failed'; provider: ClaimProvider; detail?: string }
  | { kind: 'claim_source_reconciliation_pending'; provider: ClaimProvider; state: IntegrationSourceState }
  | { kind: 'privacy_confirmed' }
  | { kind: 'privacy_confirmation_failed'; detail?: string }
  | { kind: 'permission_denied' }
  | { kind: 'rate_limited'; retryAfterSeconds?: number }
  | { kind: 'network_error' }
  | { kind: 'unknown_error'; detail?: string };

export interface IntegrationTransport {
  getWorkspace(tenantId: string, signal?: AbortSignal): Promise<IntegrationOutcome>;
  confirmWorkspace(
    tenantId: string,
    workspaceName: string,
    signal?: AbortSignal,
  ): Promise<IntegrationOutcome>;
  listIntegrations(tenantId: string, signal?: AbortSignal): Promise<IntegrationSourceState[]>;
  connectProvider(
    tenantId: string,
    provider: IntegrationProvider,
    signal?: AbortSignal,
  ): Promise<IntegrationOutcome>;
  repairProvider(
    tenantId: string,
    provider: IntegrationProvider,
    signal?: AbortSignal,
  ): Promise<IntegrationOutcome>;
  confirmPrivacyBoundary(tenantId: string, signal?: AbortSignal): Promise<IntegrationOutcome>;
}

export const COMMERCE_PROVIDERS: readonly CommerceProvider[] = [
  'shopify',
  'woocommerce',
  'stripe',
  'paypal',
];

export const CLAIM_PROVIDERS: readonly ClaimProvider[] = [
  'meta_ads',
  'google_ads',
  'tiktok_ads',
  'linkedin_ads',
  'other',
];

export function isCommerceProvider(provider: IntegrationProvider): provider is CommerceProvider {
  return (COMMERCE_PROVIDERS as readonly string[]).includes(provider);
}

export function isClaimProvider(provider: IntegrationProvider): provider is ClaimProvider {
  return (CLAIM_PROVIDERS as readonly string[]).includes(provider);
}
