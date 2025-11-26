/**
 * Mock Platform Data Generator
 * 
 * FE-UX-016: Data Integrity Monitor
 * Generates test platform data matching directive specifications
 * 
 * Default scenario:
 * - Stripe: Verified (100% match) - $9,483.77
 * - Shopify: Partial Match (85%) - $42,500.00
 * - Square: Pending (0%) - $8,250.00
 * - Google: Partial Match (92%) - $30,000.00
 */

import type { PlatformData } from '@/components/dashboard/DataIntegrityMonitor';
import type { PlatformStatus } from '@shared/schema';

/**
 * Calculate percentage of total for a platform
 */
function calculatePercentageOfTotal(
  platformRevenue: number,
  totalInCategory: number
): number {
  if (totalInCategory === 0) return 0;
  return (platformRevenue / totalInCategory) * 100;
}

/**
 * Generate mock platform data matching FE-UX-016 specifications
 */
export function generateMockPlatformData(): PlatformData[] {
  // Revenue values from directive
  const stripeRevenue = 9483.77;
  const shopifyRevenue = 42500.0;
  const squareRevenue = 8250.0;
  const googleRevenue = 30000.0;

  // Calculate totals
  const verifiedTotal = stripeRevenue;
  const unverifiedTotal = shopifyRevenue + squareRevenue + googleRevenue;

  return [
    {
      id: 'stripe_001',
      platform: 'Stripe',
      platformDisplayName: 'Stripe',
      status: 'verified' as PlatformStatus,
      matchPercentage: 100,
      revenue: stripeRevenue,
      percentageOfTotal: calculatePercentageOfTotal(stripeRevenue, verifiedTotal),
      isVerified: true,
    },
    {
      id: 'shopify_001',
      platform: 'Shopify',
      platformDisplayName: 'Shopify',
      status: 'partial' as PlatformStatus,
      matchPercentage: 85,
      revenue: shopifyRevenue,
      percentageOfTotal: calculatePercentageOfTotal(shopifyRevenue, unverifiedTotal),
      isVerified: false,
    },
    {
      id: 'square_001',
      platform: 'Square',
      platformDisplayName: 'Square',
      status: 'pending' as PlatformStatus,
      matchPercentage: 0,
      revenue: squareRevenue,
      percentageOfTotal: calculatePercentageOfTotal(squareRevenue, unverifiedTotal),
      isVerified: false,
    },
    {
      id: 'google_001',
      platform: 'Google',
      platformDisplayName: 'Google',
      status: 'partial' as PlatformStatus,
      matchPercentage: 92,
      revenue: googleRevenue,
      percentageOfTotal: calculatePercentageOfTotal(googleRevenue, unverifiedTotal),
      isVerified: false,
    },
  ];
}

/**
 * Calculate revenue totals from platform data
 */
export function calculateRevenueTotals(platformData: PlatformData[]) {
  const verified = platformData
    .filter(p => p.status === 'verified')
    .reduce((sum, p) => sum + p.revenue, 0);
  
  const unverified = platformData
    .filter(p => p.status !== 'verified')
    .reduce((sum, p) => sum + p.revenue, 0);
  
  return { 
    verified, 
    unverified,
    total: verified + unverified,
  };
}

/**
 * Generate custom platform data for testing
 */
export function generateCustomPlatformData(
  platforms: Array<{
    id: string;
    platform: string;
    platformDisplayName: string;
    status: PlatformStatus;
    matchPercentage?: number;
    revenue: number;
  }>
): PlatformData[] {
  // Calculate totals for each category
  const verifiedTotal = platforms
    .filter(p => p.status === 'verified')
    .reduce((sum, p) => sum + p.revenue, 0);
  
  const unverifiedTotal = platforms
    .filter(p => p.status !== 'verified')
    .reduce((sum, p) => sum + p.revenue, 0);

  // Map to PlatformData with calculated percentages
  return platforms.map(p => ({
    ...p,
    matchPercentage: p.matchPercentage ?? (p.status === 'verified' ? 100 : 0),
    percentageOfTotal: calculatePercentageOfTotal(
      p.revenue,
      p.status === 'verified' ? verifiedTotal : unverifiedTotal
    ),
    isVerified: p.status === 'verified',
  }));
}

/**
 * FE-UX-022: Verification Flow Progress Indicator
 * Generate mock verification flow metrics
 */
export interface VerificationFlowMetrics {
  verifiedPercentage: number;
  processingPercentage: number;
  unverifiedPercentage: number;
  transactionCount: {
    total: number;
    verified: number;
    processing: number;
    unverified: number;
  };
}

/**
 * Generate verification flow metrics from platform data
 * This calculates the flow based on transaction count, not revenue
 */
export function generateVerificationFlowMetrics(platformData: PlatformData[]): VerificationFlowMetrics {
  // Mock transaction counts based on platform status
  // In production, this would come from the backend API
  
  const transactionCounts = platformData.map(p => {
    // Generate mock transaction count based on revenue (higher revenue = more transactions)
    const baseCount = Math.floor(p.revenue / 50); // Approximately 1 transaction per $50
    
    return {
      platform: p.platform,
      count: baseCount,
      status: p.status,
    };
  });
  
  // Calculate counts by status
  const verifiedCount = transactionCounts
    .filter(t => t.status === 'verified')
    .reduce((sum, t) => sum + t.count, 0);
  
  const processingCount = transactionCounts
    .filter(t => t.status === 'partial')
    .reduce((sum, t) => sum + t.count, 0);
  
  const unverifiedCount = transactionCounts
    .filter(t => t.status === 'pending' || t.status === 'error' || t.status === 'unverified')
    .reduce((sum, t) => sum + t.count, 0);
  
  const totalCount = verifiedCount + processingCount + unverifiedCount;
  
  return {
    verifiedPercentage: totalCount > 0 ? (verifiedCount / totalCount) * 100 : 0,
    processingPercentage: totalCount > 0 ? (processingCount / totalCount) * 100 : 0,
    unverifiedPercentage: totalCount > 0 ? (unverifiedCount / totalCount) * 100 : 0,
    transactionCount: {
      total: totalCount,
      verified: verifiedCount,
      processing: processingCount,
      unverified: unverifiedCount,
    },
  };
}
