/**
 * A6-VICTOR: Canonical Mock Data
 *
 * Values matched to the golden reference screenshot (chann Comp.png).
 * 3 channels: Google Ads, Meta Ads, Pinterest Ads
 * ROAS values: 4.12, 3.65, 1.85
 * Recommendation: "Shift $8,500 from Pinterest Ads to Google Ads"
 */

import type {
  ChannelComparisonData,
  ChannelComparisonEntry,
  ChannelComparisonState,
} from '@/pages/channel-comparison/shared/types';

const googleAds: ChannelComparisonEntry = {
  channelId: 'ch_google_ads',
  channelName: 'Google Ads',
  platform: 'google_ads',
  color: '#10D98C',

  verifiedRevenue: '$58.6k',
  revenueVsAverage: '+$21.3k vs avg',
  revenueDirection: 'above',
  adSpend: '$14.2k',
  roas: '$4.12',
  roasVsAverage: '+$0.47 vs leader',
  roasDirection: 'above',
  cpa: '$28.40',
  conversions: '438',

  confidence: 'high',
  confidenceRange: { low: '$3.85', high: '$4.50', margin: 6 },
  confidenceExplanation:
    'Based on 90 days of stable data and 1,247 conversions with consistent patterns.',

  platformClaimed: '$61,300',
  verified: '$58,600',
  discrepancyPercent: 4.4,

  trend: 'up',
  trendData: [
    { date: '2026-01-17', roas: 3.82, roasLow: 3.60, roasHigh: 4.04 },
    { date: '2026-01-24', roas: 3.91, roasLow: 3.68, roasHigh: 4.14 },
    { date: '2026-01-31', roas: 4.01, roasLow: 3.78, roasHigh: 4.24 },
    { date: '2026-02-07', roas: 4.08, roasLow: 3.85, roasHigh: 4.31 },
    { date: '2026-02-14', roas: 4.12, roasLow: 3.85, roasHigh: 4.50 },
  ],

  isWinner: true,
  winnerExplanation:
    "Google's confidence range ($3.85–$4.50) does not overlap with any other channel's upper bound.",
};

const metaAds: ChannelComparisonEntry = {
  channelId: 'ch_facebook_ads',
  channelName: 'Meta Ads',
  platform: 'facebook_ads',
  color: '#3D7BF5',

  verifiedRevenue: '$32.1k',
  revenueVsAverage: '-$5.2k vs avg',
  revenueDirection: 'below',
  adSpend: '$8.8k',
  roas: '$3.65',
  roasVsAverage: '-$0.47 vs leader',
  roasDirection: 'below',
  cpa: '$34.20',
  conversions: '260',

  confidence: 'high',
  confidenceRange: { low: '$3.50', high: '$3.80', margin: 4 },
  confidenceExplanation:
    'Based on 87 days of data and 892 conversions. Slight seasonal variance noted.',

  platformClaimed: '$38,500',
  verified: '$32,100',
  discrepancyPercent: 16.6,

  trend: 'stable',
  trendData: [
    { date: '2026-01-17', roas: 3.58, roasLow: 3.42, roasHigh: 3.74 },
    { date: '2026-01-24', roas: 3.62, roasLow: 3.46, roasHigh: 3.78 },
    { date: '2026-01-31', roas: 3.55, roasLow: 3.40, roasHigh: 3.70 },
    { date: '2026-02-07', roas: 3.64, roasLow: 3.49, roasHigh: 3.79 },
    { date: '2026-02-14', roas: 3.65, roasLow: 3.50, roasHigh: 3.80 },
  ],

  isWinner: false,
};

const pinterestAds: ChannelComparisonEntry = {
  channelId: 'ch_pinterest_ads',
  channelName: 'Pinterest Ads',
  platform: 'pinterest_ads',
  color: '#F5A623',

  verifiedRevenue: '$5.7k',
  revenueVsAverage: '-$31.6k vs avg',
  revenueDirection: 'below',
  adSpend: '$3.1k',
  roas: '$1.85',
  roasVsAverage: '-$2.27 vs leader',
  roasDirection: 'below',
  cpa: '$84.00',
  conversions: '37',

  confidence: 'medium',
  confidenceRange: { low: '$1.20', high: '$2.60', margin: 38 },
  confidenceExplanation:
    'Based on 32 days of data. Attribution ranges are wide until more evidence accumulates.',

  platformClaimed: '$7,400',
  verified: '$5,700',
  discrepancyPercent: 29.8,

  trend: 'down',
  trendData: [
    { date: '2026-01-17', roas: 2.12, roasLow: 1.40, roasHigh: 2.84 },
    { date: '2026-01-24', roas: 2.05, roasLow: 1.35, roasHigh: 2.75 },
    { date: '2026-01-31', roas: 1.95, roasLow: 1.28, roasHigh: 2.62 },
    { date: '2026-02-07', roas: 1.90, roasLow: 1.24, roasHigh: 2.56 },
    { date: '2026-02-14', roas: 1.85, roasLow: 1.20, roasHigh: 2.60 },
  ],

  isWinner: false,
};

// ---------------------------------------------------------------------------
// Assembled fixtures
// ---------------------------------------------------------------------------

const readyData: ChannelComparisonData = {
  channels: [googleAds, metaAds, pinterestAds],
  dateRange: {
    start: '2026-01-15',
    end: '2026-02-14',
    label: 'Last 30 Days',
  },
  recommendation: {
    summary: 'Shift $8,500 from Pinterest Ads to Google Ads',
    confidence: 'medium',
    expectedImpact: '+$21,000 revenue impact',
  },
  lastUpdated: '2026-02-14T14:32:00Z',
};

export const VICTOR_FIXTURES: Record<string, ChannelComparisonState> = {
  ready: { status: 'ready', data: readyData },
  loading: { status: 'loading' },
  emptyNoData: { status: 'empty', variant: 'no-data-yet' },
  emptyBuildingModel: { status: 'empty', variant: 'building-model' },
  emptyInsufficientSelection: { status: 'empty', variant: 'insufficient-selection' },
  emptyNoResults: { status: 'empty', variant: 'no-results-filter' },
  error: {
    status: 'error',
    error: {
      message: 'Channel comparison data temporarily unavailable. The attribution service is processing a model update.',
      correlationId: 'err-cc-20260214-b8e2',
      retryable: true,
      action: {
        label: 'Retry now',
        onClick: () => console.log('[fixture] retry clicked'),
      },
    },
  },
};
