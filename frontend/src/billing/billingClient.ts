import type {
  BillingFetchOutcome,
  BillingPortalOutcome,
  BillingSummary,
} from './types';

let testMode: string | null = null;
let portalPending = false;
let portalAttemptCount = 0;

const FIXTURE_SUMMARY: BillingSummary = {
  tenantId: 'tenant_test_001',
  plan: {
    tier: 'design_partner',
    label: 'Design Partner',
    status: 'active',
    renewalAt: '2026-07-01T00:00:00.000Z',
    trialEndsAt: null,
  },
  paymentMethod: {
    brand: 'Visa',
    last4: '4242',
    expMonth: 12,
    expYear: 2028,
  },
  invoices: [
    {
      id: 'inv_fixture_001',
      issuedAt: '2026-06-01T00:00:00.000Z',
      amountDisplay: '$299.00',
      status: 'paid',
    },
    {
      id: 'inv_fixture_002',
      issuedAt: '2026-05-01T00:00:00.000Z',
      amountDisplay: '$299.00',
      status: 'paid',
    },
  ],
};

const PORTAL_URL = 'https://billing.skeldir.example/portal/session_fixture';

export function setBillingTestMode(mode: string | null) {
  testMode = mode;
}

export function resetBillingTestState() {
  testMode = null;
  portalPending = false;
  portalAttemptCount = 0;
}

export function getBillingPortalAttemptCount(): number {
  return portalAttemptCount;
}

export async function fetchBillingSummary(tenantId: string): Promise<BillingFetchOutcome> {
  await delay(10);

  if (testMode === 'network_error') {
    return { kind: 'network_error' };
  }
  if (testMode === 'portal_unavailable') {
    return { kind: 'portal_unavailable' };
  }
  if (testMode === 'permission_denied') {
    return { kind: 'permission_denied' };
  }
  if (testMode === 'cross_tenant_billing') {
    return { kind: 'cross_tenant_denied' };
  }
  if (testMode === 'empty') {
    return { kind: 'empty' };
  }
  if (testMode === 'loading') {
    return { kind: 'loading' };
  }

  if (tenantId !== FIXTURE_SUMMARY.tenantId && tenantId !== 'tenant_cross_check') {
    return { kind: 'cross_tenant_denied' };
  }

  return {
    kind: 'loaded',
    summary: { ...FIXTURE_SUMMARY, tenantId },
  };
}

export async function initiateManageBilling(): Promise<BillingPortalOutcome> {
  if (portalPending || portalAttemptCount > 0) {
    return { kind: 'already_pending' };
  }

  portalAttemptCount += 1;
  portalPending = true;

  if (testMode === 'network_error') {
    portalPending = false;
    return { kind: 'network_error' };
  }
  if (testMode === 'portal_unavailable') {
    portalPending = false;
    return { kind: 'portal_unavailable' };
  }
  if (testMode === 'permission_denied') {
    portalPending = false;
    return { kind: 'permission_denied' };
  }

  await delay(20);
  portalPending = false;

  return { kind: 'success', portalUrl: PORTAL_URL };
}

function delay(ms: number) {
  return new Promise<void>((resolve) => {
    setTimeout(resolve, ms);
  });
}

export function getFixturePortalUrl(): string {
  return PORTAL_URL;
}
