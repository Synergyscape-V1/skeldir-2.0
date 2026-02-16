/**
 * SKELDIR CHANNEL DETAIL — SHARED MOCK DATA
 *
 * Consumed by all 5 Design Agent Storybook stories.
 * All values pre-formatted as they would arrive from the API.
 * No calculations needed client-side.
 */

import type { ChannelDetailData, ChannelDetailState } from './types';

// ─────────────────────────────────────────────────────────────────
// TREND DATA (30 days of Facebook performance)
// ─────────────────────────────────────────────────────────────────

const generateTrendData = (): ChannelDetailData['trendData'] => {
  const data: ChannelDetailData['trendData'] = [];
  const baseRevenue = 1200;
  const baseSpend = 380;
  // baseRoas used indirectly via revenue/spend ratio
  for (let i = 0; i < 30; i++) {
    const date = new Date(2026, 0, i + 1);
    const dayOfWeek = date.getDay();
    const weekendDip = (dayOfWeek === 0 || dayOfWeek === 6) ? 0.78 : 1.0;
    const trend = 1 + (i / 30) * 0.15; // 15% upward trend over the month
    const noise = 0.92 + Math.random() * 0.16;

    const revenue = Math.round(baseRevenue * weekendDip * trend * noise);
    const spend = Math.round(baseSpend * weekendDip * trend * (0.95 + Math.random() * 0.1));
    const roas = +(revenue / spend).toFixed(2);
    const roasLow = +(roas * 0.85).toFixed(2);
    const roasHigh = +(roas * 1.18).toFixed(2);

    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

    data.push({
      date: date.toISOString().split('T')[0],
      dateFormatted: `${months[date.getMonth()]} ${date.getDate()}`,
      revenue,
      revenueFormatted: `$${revenue.toLocaleString()}`,
      spend,
      spendFormatted: `$${spend.toLocaleString()}`,
      roas,
      roasFormatted: `${roas}x`,
      roasRangeLow: roasLow,
      roasRangeLowFormatted: `${roasLow}x`,
      roasRangeHigh: roasHigh,
      roasRangeHighFormatted: `${roasHigh}x`,
    });
  }
  return data;
};

// ─────────────────────────────────────────────────────────────────
// READY STATE — Full data for Facebook Ads channel
// ─────────────────────────────────────────────────────────────────

export const MOCK_CHANNEL_DATA: ChannelDetailData = {
  channel: {
    id: 'meta',
    name: 'Meta Ads',
    platform: 'meta',
    status: 'active',
    connectedSince: '2025-09-15',
  },

  dateRange: {
    start: '2026-01-01',
    end: '2026-01-31',
    label: 'Jan 1 – Jan 31, 2026',
  },

  performance: {
    revenue: 42850,
    revenueFormatted: '$42,850',
    revenueDelta: '+12.3% vs prev period',
    spend: 12400,
    spendFormatted: '$12,400',
    spendDelta: '+5.1% vs prev period',
    roas: 3.46,
    roasFormatted: '3.46x',
    roasDelta: '+0.40 vs Google',
    conversions: 1247,
    conversionsFormatted: '1,247',
    conversionsDelta: '+8.2% vs prev period',
    cpa: 9.94,
    cpaFormatted: '$9.94',
    cpaDelta: '-$1.20 vs prev period',
  },

  verification: {
    platformClaimed: 45200,
    platformClaimedFormatted: '$45,200',
    verified: 42850,
    verifiedFormatted: '$42,850',
    discrepancy: -2350,
    discrepancyPercent: -5.2,
    discrepancyFormatted: '-5.2%',
    transactionCount: 1247,
    transactionCountFormatted: '1,247 transactions',
    revenueSource: 'Stripe',
  },

  confidenceRange: {
    low: 2.80,
    lowFormatted: '$2.80',
    high: 3.80,
    highFormatted: '$3.80',
    point: 3.46,
    pointFormatted: '$3.46',
    level: 'high',
    explanation: 'Based on 28 days of stable data and 1,247 conversions with consistent patterns.',
    margin: 10,
    daysOfData: 28,
    conversionsUsed: 1247,
  },

  trendData: generateTrendData(),

  modelInfo: {
    version: 47,
    lastUpdated: '2026-01-31T14:30:00Z',
    lastUpdatedFormatted: '2 hours ago',
    nextUpdate: 'in 22 hours',
  },
};

// ─────────────────────────────────────────────────────────────────
// MEDIUM CONFIDENCE VARIANT (Google Ads)
// ─────────────────────────────────────────────────────────────────

export const MOCK_CHANNEL_DATA_MEDIUM: ChannelDetailData = {
  ...MOCK_CHANNEL_DATA,
  channel: {
    id: 'google',
    name: 'Google Ads',
    platform: 'google',
    status: 'active',
    connectedSince: '2025-11-20',
  },
  performance: {
    ...MOCK_CHANNEL_DATA.performance,
    revenue: 31200,
    revenueFormatted: '$31,200',
    revenueDelta: '+4.1% vs prev period',
    roas: 3.06,
    roasFormatted: '3.06x',
    roasDelta: '-0.40 vs Facebook',
  },
  verification: {
    ...MOCK_CHANNEL_DATA.verification,
    discrepancyPercent: -11.4,
    discrepancyFormatted: '-11.4%',
  },
  confidenceRange: {
    ...MOCK_CHANNEL_DATA.confidenceRange,
    level: 'medium',
    low: 2.20,
    lowFormatted: '$2.20',
    high: 3.90,
    highFormatted: '$3.90',
    explanation: 'Based on 10 days of data. Add 4 more days to increase confidence.',
    margin: 25,
    daysOfData: 10,
  },
};

// ─────────────────────────────────────────────────────────────────
// STATE PRESETS — for Storybook stories
// ─────────────────────────────────────────────────────────────────

export const MOCK_STATES: Record<string, ChannelDetailState> = {
  ready: {
    status: 'ready',
    data: MOCK_CHANNEL_DATA,
  },

  readyMedium: {
    status: 'ready',
    data: MOCK_CHANNEL_DATA_MEDIUM,
  },

  loading: {
    status: 'loading',
  },

  emptyNoData: {
    status: 'empty',
    emptyVariant: 'no-data-yet',
  },

  emptyBuilding: {
    status: 'empty',
    emptyVariant: 'building-model',
    currentDay: 6,
  },

  emptyFiltered: {
    status: 'empty',
    emptyVariant: 'no-results-filter',
  },

  emptyLocked: {
    status: 'empty',
    emptyVariant: 'feature-locked',
  },

  error: {
    status: 'error',
    error: {
      title: 'Dashboard timed out.',
      message: 'The attribution data request exceeded 30 seconds. Your data is intact.',
      correlationId: 'sk-err-20260131-7f3a',
      retryable: true,
      action: {
        label: 'Report issue #sk-err-20260131-7f3a',
        onClick: () => console.log('Report issue clicked'),
      },
    },
  },

  errorNonRetryable: {
    status: 'error',
    error: {
      title: 'Connection to Facebook failed.',
      message: 'Check that Skeldir has the required permissions in your Facebook Business Account.',
      correlationId: 'sk-err-20260131-9b2c',
      retryable: false,
      action: {
        label: 'Get Help',
        onClick: () => console.log('Get help clicked'),
      },
    },
  },
};
