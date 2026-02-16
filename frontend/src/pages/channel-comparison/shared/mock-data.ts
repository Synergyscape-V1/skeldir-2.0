/**
 * Channel Comparison — Deterministic Mock Data
 *
 * Used by all 5 Design Agents + Storybook stories.
 * All values are pre-formatted per Zero Mental Math principle.
 * No agent may modify these fixtures — they are the invariant test data.
 */

import type {
  ChannelComparisonData,
  ChannelComparisonEntry,
  ChannelComparisonState,
} from './types';

// ---------------------------------------------------------------------------
// Channel Entries
// ---------------------------------------------------------------------------

const googleAds: ChannelComparisonEntry = {
  channelId: 'ch_google_ads',
  channelName: 'Google Ads',
  platform: 'google_ads',
  color: '#10D98C',

  verifiedRevenue: '$48,200',
  revenueVsAverage: '+$12,830 vs avg',
  revenueDirection: 'above',
  adSpend: '$12,450',
  roas: '$3.87',
  roasVsAverage: '+$1.15 vs avg',
  roasDirection: 'above',
  cpa: '$28.40',
  conversions: '438',

  confidence: 'high',
  confidenceRange: { low: '$3.65', high: '$4.10', margin: 6 },
  confidenceExplanation:
    'Based on 90 days of stable data and 1,247 conversions with consistent patterns.',

  platformClaimed: '$51,300',
  verified: '$48,200',
  discrepancyPercent: 6.4,

  trend: 'up',
  trendData: [
    { date: '2026-01-17', roas: 3.52, roasLow: 3.30, roasHigh: 3.74 },
    { date: '2026-01-24', roas: 3.61, roasLow: 3.38, roasHigh: 3.84 },
    { date: '2026-01-31', roas: 3.74, roasLow: 3.50, roasHigh: 3.98 },
    { date: '2026-02-07', roas: 3.80, roasLow: 3.58, roasHigh: 4.02 },
    { date: '2026-02-14', roas: 3.87, roasLow: 3.65, roasHigh: 4.10 },
  ],

  isWinner: true,
  winnerExplanation:
    "Google's confidence range ($3.65–$4.10) does not overlap with any other channel's upper bound.",
};

const metaAds: ChannelComparisonEntry = {
  channelId: 'ch_facebook_ads',
  channelName: 'Meta Ads',
  platform: 'facebook_ads',
  color: '#3D7BF5',

  verifiedRevenue: '$28,500',
  revenueVsAverage: '-$6,870 vs avg',
  revenueDirection: 'below',
  adSpend: '$8,900',
  roas: '$3.20',
  roasVsAverage: '+$0.48 vs avg',
  roasDirection: 'above',
  cpa: '$34.20',
  conversions: '260',

  confidence: 'high',
  confidenceRange: { low: '$2.95', high: '$3.45', margin: 8 },
  confidenceExplanation:
    'Based on 87 days of data and 892 conversions. Slight seasonal variance noted.',

  platformClaimed: '$34,100',
  verified: '$28,500',
  discrepancyPercent: 19.6,

  trend: 'stable',
  trendData: [
    { date: '2026-01-17', roas: 3.18, roasLow: 2.92, roasHigh: 3.44 },
    { date: '2026-01-24', roas: 3.22, roasLow: 2.96, roasHigh: 3.48 },
    { date: '2026-01-31', roas: 3.15, roasLow: 2.90, roasHigh: 3.40 },
    { date: '2026-02-07', roas: 3.24, roasLow: 2.99, roasHigh: 3.49 },
    { date: '2026-02-14', roas: 3.20, roasLow: 2.95, roasHigh: 3.45 },
  ],

  isWinner: false,
};

const tiktokAds: ChannelComparisonEntry = {
  channelId: 'ch_tiktok_ads',
  channelName: 'TikTok Ads',
  platform: 'tiktok_ads',
  color: '#F5A623',

  verifiedRevenue: '$6,800',
  revenueVsAverage: '-$28,570 vs avg',
  revenueDirection: 'below',
  adSpend: '$3,200',
  roas: '$2.13',
  roasVsAverage: '-$0.59 vs avg',
  roasDirection: 'below',
  cpa: '$52.80',
  conversions: '61',

  confidence: 'medium',
  confidenceRange: { low: '$1.60', high: '$2.65', margin: 25 },
  confidenceExplanation:
    'Based on 45 days of data. Add 15 more days to narrow the confidence range.',

  platformClaimed: '$8,400',
  verified: '$6,800',
  discrepancyPercent: 23.5,

  trend: 'down',
  trendData: [
    { date: '2026-01-17', roas: 2.45, roasLow: 1.84, roasHigh: 3.06 },
    { date: '2026-01-24', roas: 2.38, roasLow: 1.78, roasHigh: 2.98 },
    { date: '2026-01-31', roas: 2.22, roasLow: 1.66, roasHigh: 2.78 },
    { date: '2026-02-07', roas: 2.18, roasLow: 1.63, roasHigh: 2.73 },
    { date: '2026-02-14', roas: 2.13, roasLow: 1.60, roasHigh: 2.65 },
  ],

  isWinner: false,
};

const pinterestAds: ChannelComparisonEntry = {
  channelId: 'ch_pinterest_ads',
  channelName: 'Pinterest Ads',
  platform: 'pinterest_ads',
  color: '#F54E8B',

  verifiedRevenue: '$3,100',
  revenueVsAverage: '-$32,270 vs avg',
  revenueDirection: 'below',
  adSpend: '$2,100',
  roas: '$1.48',
  roasVsAverage: '-$1.24 vs avg',
  roasDirection: 'below',
  cpa: '$84.00',
  conversions: '25',

  confidence: 'low',
  confidenceRange: { low: '$0.90', high: '$2.10', margin: 41 },
  confidenceExplanation:
    'Only 25 days of data available. Attribution ranges are wide until more evidence accumulates.',

  platformClaimed: '$4,200',
  verified: '$3,100',
  discrepancyPercent: 35.5,

  trend: 'down',
  trendData: [
    { date: '2026-01-17', roas: 1.72, roasLow: 0.95, roasHigh: 2.49 },
    { date: '2026-01-24', roas: 1.65, roasLow: 0.92, roasHigh: 2.38 },
    { date: '2026-01-31', roas: 1.58, roasLow: 0.90, roasHigh: 2.26 },
    { date: '2026-02-07', roas: 1.52, roasLow: 0.88, roasHigh: 2.16 },
    { date: '2026-02-14', roas: 1.48, roasLow: 0.90, roasHigh: 2.10 },
  ],

  isWinner: false,
};

// ---------------------------------------------------------------------------
// Assembled Fixtures
// ---------------------------------------------------------------------------

const readyData: ChannelComparisonData = {
  channels: [googleAds, metaAds, tiktokAds, pinterestAds],
  dateRange: {
    start: '2026-01-15',
    end: '2026-02-14',
    label: 'Last 30 Days',
  },
  recommendation: {
    summary: 'Shift $2,100 from Pinterest to Google Search',
    confidence: 'medium',
    expectedImpact: '+$8,100 revenue (+9.2%)',
  },
  lastUpdated: '2026-02-14T14:32:00Z',
};

export const COMPARISON_FIXTURES: Record<string, ChannelComparisonState> = {
  ready: {
    status: 'ready',
    data: readyData,
  },

  loading: {
    status: 'loading',
  },

  emptyNoData: {
    status: 'empty',
    variant: 'no-data-yet',
  },

  emptyBuildingModel: {
    status: 'empty',
    variant: 'building-model',
  },

  emptyInsufficientSelection: {
    status: 'empty',
    variant: 'insufficient-selection',
  },

  emptyNoResults: {
    status: 'empty',
    variant: 'no-results-filter',
  },

  error: {
    status: 'error',
    error: {
      message:
        'Channel comparison data temporarily unavailable. The attribution service is processing a model update.',
      correlationId: 'err-cc-20260214-b8e2',
      retryable: true,
      action: {
        label: 'Retry now',
        onClick: () => console.log('[fixture] retry clicked'),
      },
    },
  },
};

/**
 * Helper to get only the ready-state data for component development.
 */
export function getReadyData(): ChannelComparisonData {
  return readyData;
}

/**
 * Helper to get individual channel entries for isolated testing.
 */
export const CHANNEL_ENTRIES = {
  google: googleAds,
  meta: metaAds,
  tiktok: tiktokAds,
  pinterest: pinterestAds,
} as const;
