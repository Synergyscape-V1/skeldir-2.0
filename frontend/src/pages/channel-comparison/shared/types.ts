/**
 * Channel Comparison — Shared Type Contract
 *
 * All 5 Design Agents implement this identically in behavior.
 * Source: Plan §2 "Channel Comparison Functional Contract"
 * Source: Master Skill state machine + confidence model
 *
 * DO NOT MODIFY — this is the invariant contract.
 */

import type { ConfidenceTier, TrendDirection, SkeldirError, EmptyVariant } from '@/agents/shared-types';

// Re-export for convenience
export type { ConfidenceTier, TrendDirection, SkeldirError, EmptyVariant };

// ---------------------------------------------------------------------------
// Channel Comparison Data Contract
// ---------------------------------------------------------------------------

export interface ChannelComparisonData {
  channels: ChannelComparisonEntry[];
  dateRange: { start: string; end: string; label: string };
  recommendation?: {
    summary: string;
    confidence: ConfidenceTier;
    expectedImpact: string;
  };
  lastUpdated: string;
}

export interface ChannelComparisonEntry {
  channelId: string;
  channelName: string;
  platform: string;
  color: string;

  // All values pre-formatted (Zero Mental Math)
  verifiedRevenue: string;
  revenueVsAverage: string;
  revenueDirection: 'above' | 'below' | 'at';
  adSpend: string;
  roas: string;
  roasVsAverage: string;
  roasDirection: 'above' | 'below' | 'at';
  cpa: string;
  conversions: string;

  // Confidence
  confidence: ConfidenceTier;
  confidenceRange: { low: string; high: string; margin: number };
  confidenceExplanation: string;

  // Verification
  platformClaimed: string;
  verified: string;
  discrepancyPercent: number;

  // Trend
  trend: TrendDirection;
  trendData: Array<{ date: string; roas: number; roasLow: number; roasHigh: number }>;

  // Winner determination (pre-computed by backend)
  isWinner?: boolean;
  winnerExplanation?: string;
}

// ---------------------------------------------------------------------------
// State Machine
// ---------------------------------------------------------------------------

export type ComparisonEmptyVariant =
  | 'no-data-yet'
  | 'building-model'
  | 'insufficient-selection'
  | 'no-results-filter';

export type ChannelComparisonState =
  | { status: 'loading' }
  | { status: 'empty'; variant: ComparisonEmptyVariant }
  | { status: 'error'; error: SkeldirError }
  | { status: 'ready'; data: ChannelComparisonData };
