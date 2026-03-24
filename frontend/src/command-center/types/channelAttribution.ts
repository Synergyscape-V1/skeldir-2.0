/**
 * Channel Performance / Attribution table row (Command Center §3.9)
 */

export type VerificationState = 'verified' | 'partial' | 'unverified';

export type ConfidenceBucket = 'narrow' | 'medium' | 'wide';

export interface ChannelRoasModel {
  estimate: number;
  lower: number;
  upper: number;
  bucket: ConfidenceBucket;
  formattedEstimate: string;
  /** Optional override for tooltip copy */
  actionImplication?: string;
}

export interface ChannelTrendModel {
  direction: 'up' | 'down' | 'neutral';
  /** e.g. "↓ 5%" */
  label: string;
  /** Signed numeric for sorting (e.g. +8 or -5) */
  sortValue: number;
  comparisonHint?: string;
}

export interface ChannelAttributionRow {
  channelId: string;
  channelName: string;
  platform: string;
  spend: string;
  verifiedRevenue: string;
  verifiedStatus: VerificationState;
  /** e.g. "Stripe" */
  verificationSource?: string;
  /** Shown in verification tooltip */
  lastVerifiedLabel?: string;
  roas: ChannelRoasModel;
  confidence: ConfidenceBucket;
  /** Hover on confidence badge */
  confidenceActionImplication?: string;
  trend: ChannelTrendModel;
  attributionMethod?: string;
}
