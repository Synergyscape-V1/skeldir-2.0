import type { DataReconciliationStatus, UnmatchedTransaction, PlatformVariance } from '@shared/schema';

/**
 * Generate mock data for Data Reconciliation Status component
 * FE-UX-024: Mock data matching the directive specifications
 * FE-UX-026: Added platform IDs and daysPending
 */
export function generateMockReconciliationData(): DataReconciliationStatus {
  const platformVariances: PlatformVariance[] = [
    {
      id: 'stripe',
      name: 'Stripe',
      unmatchedCount: 0,
      matchPercentage: 100.0,
      totalTransactions: 1523,
      unmatchedRevenue: 0.00,
      status: 'verified',
    },
    {
      id: 'shopify',
      name: 'Shopify',
      unmatchedCount: 165,
      matchPercentage: 85.0,
      totalTransactions: 1094,
      unmatchedRevenue: 42500.00,
      status: 'partial',
    },
    {
      id: 'square',
      name: 'Square',
      unmatchedCount: 12,
      matchPercentage: 92.0,
      totalTransactions: 150,
      unmatchedRevenue: 8250.00,
      status: 'partial',
    },
    {
      id: 'google-ads',
      name: 'Google Ads',
      unmatchedCount: 9,
      matchPercentage: 97.0,
      totalTransactions: 300,
      unmatchedRevenue: 3120.00,
      status: 'verified',
    },
  ];

  // Helper to calculate days pending
  const calculateDaysPending = (date: string): number => {
    const now = new Date();
    const txDate = new Date(date);
    const diffMs = now.getTime() - txDate.getTime();
    return Math.floor(diffMs / (1000 * 60 * 60 * 24));
  };

  const unmatchedTransactions: UnmatchedTransaction[] = [
    // Shopify transactions
    {
      id: 'TXN-SHOP-2025-001234',
      platform: 'Shopify',
      amount: 1249.99,
      date: '2025-10-10T14:32:00Z',
      transactionType: 'payment',
      reason: 'Payment date mismatch: expected 10/10, received 10/12',
      status: 'investigating',
      createdAt: '2025-10-10T14:32:00Z',
      lastModified: '2025-10-12T10:15:00Z',
      daysPending: calculateDaysPending('2025-10-10T14:32:00Z'),
    },
    {
      id: 'TXN-SHOP-2025-001235',
      platform: 'Shopify',
      amount: 849.50,
      date: '2025-10-10T13:20:00Z',
      transactionType: 'payment',
      reason: 'Amount variance: $2.35 difference detected',
      status: 'variance_detected',
      createdAt: '2025-10-10T13:20:00Z',
      lastModified: '2025-10-11T09:30:00Z',
      daysPending: calculateDaysPending('2025-10-10T13:20:00Z'),
    },
    {
      id: 'TXN-SHOP-2025-001236',
      platform: 'Shopify',
      amount: 599.00,
      date: '2025-10-09T16:45:00Z',
      transactionType: 'payment',
      reason: 'Missing transaction record in ledger',
      status: 'pending_data',
      createdAt: '2025-10-09T16:45:00Z',
      lastModified: '2025-10-10T14:20:00Z',
      daysPending: calculateDaysPending('2025-10-09T16:45:00Z'),
    },
    {
      id: 'TXN-SHOP-2025-001237',
      platform: 'Shopify',
      amount: 1950.00,
      date: '2025-10-09T11:30:00Z',
      transactionType: 'payment',
      reason: 'Duplicate transaction ID across systems',
      status: 'investigating',
      createdAt: '2025-10-09T11:30:00Z',
      lastModified: '2025-10-11T16:45:00Z',
      daysPending: calculateDaysPending('2025-10-09T11:30:00Z'),
    },
    {
      id: 'TXN-SHOP-2025-001238',
      platform: 'Shopify',
      amount: 425.75,
      date: '2025-10-08T14:15:00Z',
      transactionType: 'payment',
      reason: 'Currency conversion mismatch',
      status: 'variance_detected',
      createdAt: '2025-10-08T14:15:00Z',
      lastModified: '2025-10-09T11:30:00Z',
      daysPending: calculateDaysPending('2025-10-08T14:15:00Z'),
    },
    {
      id: 'TXN-SHOP-2025-001239',
      platform: 'Shopify',
      amount: 3200.00,
      date: '2025-10-08T09:00:00Z',
      transactionType: 'payment',
      reason: 'Payment gateway timeout during reconciliation',
      status: 'pending_data',
      createdAt: '2025-10-08T09:00:00Z',
      lastModified: '2025-10-10T08:15:00Z',
      daysPending: calculateDaysPending('2025-10-08T09:00:00Z'),
    },
    
    // Square transactions
    {
      id: 'TXN-SQ-2025-000891',
      platform: 'Square',
      amount: 750.00,
      date: '2025-10-11T10:20:00Z',
      transactionType: 'refund',
      reason: 'Refund not reflected in reconciliation',
      status: 'investigating',
      createdAt: '2025-10-11T10:20:00Z',
      lastModified: '2025-10-12T14:30:00Z',
      daysPending: calculateDaysPending('2025-10-11T10:20:00Z'),
    },
    {
      id: 'TXN-SQ-2025-000892',
      platform: 'Square',
      amount: 325.50,
      date: '2025-10-10T15:45:00Z',
      transactionType: 'payment',
      reason: 'Tax calculation discrepancy',
      status: 'variance_detected',
      createdAt: '2025-10-10T15:45:00Z',
      lastModified: '2025-10-11T10:20:00Z',
      daysPending: calculateDaysPending('2025-10-10T15:45:00Z'),
    },
    {
      id: 'TXN-SQ-2025-000893',
      platform: 'Square',
      amount: 1100.00,
      date: '2025-10-09T12:30:00Z',
      transactionType: 'payment',
      reason: 'Batch settlement timing mismatch',
      status: 'pending_data',
      createdAt: '2025-10-09T12:30:00Z',
      lastModified: '2025-10-10T09:45:00Z',
      daysPending: calculateDaysPending('2025-10-09T12:30:00Z'),
    },
    {
      id: 'TXN-SQ-2025-000894',
      platform: 'Square',
      amount: 499.99,
      date: '2025-10-08T16:00:00Z',
      transactionType: 'adjustment',
      reason: 'Manual adjustment not synced',
      status: 'investigating',
      createdAt: '2025-10-08T16:00:00Z',
      lastModified: '2025-10-09T13:15:00Z',
      daysPending: calculateDaysPending('2025-10-08T16:00:00Z'),
    },
    
    // Google Ads transactions
    {
      id: 'TXN-GADS-2025-005621',
      platform: 'Google Ads',
      amount: 850.00,
      date: '2025-10-11T08:30:00Z',
      transactionType: 'adjustment',
      reason: 'Ad spend attribution delay',
      status: 'pending_data',
      createdAt: '2025-10-11T08:30:00Z',
      lastModified: '2025-10-12T11:45:00Z',
      daysPending: calculateDaysPending('2025-10-11T08:30:00Z'),
    },
    {
      id: 'TXN-GADS-2025-005622',
      platform: 'Google Ads',
      amount: 1250.00,
      date: '2025-10-10T09:15:00Z',
      transactionType: 'adjustment',
      reason: 'Conversion tracking discrepancy',
      status: 'variance_detected',
      createdAt: '2025-10-10T09:15:00Z',
      lastModified: '2025-10-11T15:30:00Z',
      daysPending: calculateDaysPending('2025-10-10T09:15:00Z'),
    },
    {
      id: 'TXN-GADS-2025-005623',
      platform: 'Google Ads',
      amount: 675.00,
      date: '2025-10-09T14:45:00Z',
      transactionType: 'adjustment',
      reason: 'Budget adjustment timing issue',
      status: 'investigating',
      createdAt: '2025-10-09T14:45:00Z',
      lastModified: '2025-10-10T12:00:00Z',
      daysPending: calculateDaysPending('2025-10-09T14:45:00Z'),
    },
  ];

  // Calculate overall match percentage based on platform data
  const totalTransactions = platformVariances.reduce((sum, p) => sum + p.totalTransactions, 0);
  const totalMatched = platformVariances.reduce((sum, p) => sum + (p.totalTransactions - p.unmatchedCount), 0);
  const matchPercentage = Math.round((totalMatched / totalTransactions) * 100);
  const variance = 100 - matchPercentage;
  const totalUnmatched = platformVariances.reduce((sum, p) => sum + p.unmatchedCount, 0);

  return {
    matchPercentage,
    variance,
    unmatchedCount: totalUnmatched,
    platformVariances,
    unmatchedTransactions,
    lastSyncTime: '2 minutes ago',
  };
}
