export type BillingPlanTier = 'design_partner' | 'growth' | 'enterprise';

export type BillingStatus =
  | 'active'
  | 'trialing'
  | 'past_due'
  | 'canceled'
  | 'paused';

export type BillingInvoiceStatus = 'paid' | 'open' | 'void';

export interface BillingPlanSummary {
  tier: BillingPlanTier;
  label: string;
  status: BillingStatus;
  renewalAt: string | null;
  trialEndsAt: string | null;
}

export interface BillingPaymentMethodSummary {
  brand: string;
  last4: string;
  expMonth: number;
  expYear: number;
}

export interface BillingInvoiceRow {
  id: string;
  issuedAt: string;
  amountDisplay: string;
  status: BillingInvoiceStatus;
}

export interface BillingSummary {
  tenantId: string;
  plan: BillingPlanSummary;
  paymentMethod: BillingPaymentMethodSummary | null;
  invoices: BillingInvoiceRow[];
}

export type BillingFetchOutcome =
  | { kind: 'loaded'; summary: BillingSummary }
  | { kind: 'loading' }
  | { kind: 'empty' }
  | { kind: 'permission_denied' }
  | { kind: 'network_error' }
  | { kind: 'portal_unavailable' }
  | { kind: 'cross_tenant_denied' };

export type BillingPortalOutcome =
  | { kind: 'pending'; portalUrl: string }
  | { kind: 'success'; portalUrl: string }
  | { kind: 'permission_denied' }
  | { kind: 'network_error' }
  | { kind: 'portal_unavailable' }
  | { kind: 'already_pending' };
