/**
 * D2-P3 Deterministic State Fixtures
 *
 * These fixtures provide deterministic props to render each data-bearing
 * D2 composite in every state (loading / empty / error / populated).
 *
 * Consumed by the upcoming D2 composites harness route (/d2/composites)
 * and available for ad-hoc local testing.
 *
 * Contract: every fixture set has exactly 4 keys: loading, empty, error, populated.
 */

import type { DataCompositeStatus } from './index';

// ---------------------------------------------------------------------------
// ActivitySection fixtures
// ---------------------------------------------------------------------------

export const activitySectionFixtures = {
  loading: {
    status: 'loading' as DataCompositeStatus,
    data: [],
    onRetry: () => {},
  },
  empty: {
    status: 'empty' as DataCompositeStatus,
    data: [],
    onRetry: () => {},
  },
  error: {
    status: 'error' as DataCompositeStatus,
    data: [],
    onRetry: () => { console.log('[fixture] ActivitySection retry'); },
  },
  populated: {
    status: 'success' as DataCompositeStatus,
    data: [
      { id: 1, action: 'Invoice #4821 reconciled with Stripe', time: '2026-02-10T14:30:00Z' },
      { id: 2, action: 'Platform sync completed (Shopify)', time: '2026-02-10T13:15:00Z' },
      { id: 3, action: 'Variance flagged on PayPal channel', time: '2026-02-10T11:02:00Z' },
    ],
    onRetry: () => {},
  },
} as const;

// ---------------------------------------------------------------------------
// DataConfidenceBar fixtures
// ---------------------------------------------------------------------------

export const dataConfidenceBarFixtures = {
  loading: {
    status: 'loading' as DataCompositeStatus,
    overallConfidence: 0,
    verifiedTransactionPercentage: 0,
    lastUpdated: '',
    trend: 'stable' as const,
    onRetry: () => {},
  },
  empty: {
    status: 'empty' as DataCompositeStatus,
    overallConfidence: 0,
    verifiedTransactionPercentage: 0,
    lastUpdated: '',
    trend: 'stable' as const,
    onRetry: () => {},
  },
  error: {
    status: 'error' as DataCompositeStatus,
    overallConfidence: 0,
    verifiedTransactionPercentage: 0,
    lastUpdated: '',
    trend: 'stable' as const,
    onRetry: () => { console.log('[fixture] DataConfidenceBar retry'); },
  },
  populated: {
    status: 'success' as DataCompositeStatus,
    overallConfidence: 87,
    verifiedTransactionPercentage: 45,
    lastUpdated: '2 minutes ago',
    trend: 'increasing' as const,
    onRetry: () => {},
  },
} as const;

// ---------------------------------------------------------------------------
// UserInfoCard fixtures
// ---------------------------------------------------------------------------

export const userInfoCardFixtures = {
  loading: {
    status: 'loading' as DataCompositeStatus,
    username: '',
    email: '',
    onRetry: () => {},
  },
  empty: {
    status: 'empty' as DataCompositeStatus,
    username: '',
    email: '',
    onRetry: () => {},
  },
  error: {
    status: 'error' as DataCompositeStatus,
    username: '',
    email: '',
    onRetry: () => { console.log('[fixture] UserInfoCard retry'); },
  },
  populated: {
    status: 'success' as DataCompositeStatus,
    username: 'alice.chen',
    email: 'alice@skeldir.io',
    lastLogin: '2026-02-10T09:30:00Z',
    onRetry: () => {},
  },
} as const;

// ---------------------------------------------------------------------------
// All fixture sets (for programmatic iteration in the harness)
// ---------------------------------------------------------------------------

export const allDataBearingFixtures = {
  ActivitySection: activitySectionFixtures,
  DataConfidenceBar: dataConfidenceBarFixtures,
  UserInfoCard: userInfoCardFixtures,
} as const;

/** State keys in render order */
export const stateKeys = ['loading', 'empty', 'error', 'populated'] as const;
