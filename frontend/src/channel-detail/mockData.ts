export const sparklines = {
  spend: [19200,19800,20100,20400,19900,21000,21200,20800,21500,21900,21600,22000,21800,22100,22300,22000,22400,22200,22500,22800,22600,22900,22700,23000,22800,22400,22600,22900,22700,22400],
  verifiedRevenue: [62000,63500,62800,64000,63200,65000,64500,66000,65200,66800,66000,67500,67000,68200,68000,69000,68500,69800,69200,70000,70500,71000,70800,71500,71200,71800,71500,72000,71800,71680],
  roas: [2.80,2.85,2.82,2.90,2.88,2.95,2.92,3.00,2.98,3.05,3.02,3.10,3.08,3.12,3.10,3.15,3.12,3.18,3.15,3.20,3.18,3.22,3.19,3.24,3.21,3.20,3.22,3.25,3.22,3.20],
  attributionWeight: [0.31,0.315,0.318,0.32,0.322,0.325,0.328,0.33,0.332,0.335,0.338,0.34,0.338,0.341,0.340,0.342,0.341,0.343,0.342,0.344,0.343,0.345,0.343,0.344,0.343,0.342,0.343,0.344,0.342,0.342],
  agreementScore: [0.88,0.89,0.90,0.91,0.90,0.92,0.91,0.93,0.92,0.93,0.93,0.94,0.93,0.94,0.93,0.94,0.94,0.95,0.94,0.95,0.94,0.95,0.94,0.95,0.94,0.94,0.95,0.94,0.94,0.94],
};

/** URL/route channel ids from Command Center table → display name (and optional numeric tweaks). */
const CHANNEL_META: Record<string, { channelName: string; spend: number; verifiedRevenue: number; attributionWeight: number; roasEst: number; roasLow: number; roasUp: number }> = {
  google_ads: { channelName: 'Google Ads', spend: 22400, verifiedRevenue: 71680, attributionWeight: 0.342, roasEst: 3.20, roasLow: 2.80, roasUp: 3.60 },
  meta: { channelName: 'Meta Ads', spend: 59000, verifiedRevenue: 97450, attributionWeight: 0.221, roasEst: 4.00, roasLow: 3.20, roasUp: 4.80 },
  tiktok: { channelName: 'TikTok Ads', spend: 29800, verifiedRevenue: 97450, attributionWeight: 0.184, roasEst: 2.80, roasLow: 1.60, roasUp: 4.00 },
  linkedin: { channelName: 'LinkedIn Ads', spend: 12700, verifiedRevenue: 17800, attributionWeight: 0.128, roasEst: 1.80, roasLow: 1.40, roasUp: 2.20 },
  pinterest: { channelName: 'Pinterest Ads', spend: 2400, verifiedRevenue: 7450, attributionWeight: 0.125, roasEst: 2.80, roasLow: 1.40, roasUp: 4.20 },
};

function formatCurrency(n: number) {
  return '$' + n.toLocaleString();
}

function buildChannelAttribution(urlChannelId: string) {
  const meta = CHANNEL_META[urlChannelId] ?? CHANNEL_META.google_ads;
  const channelName = meta.channelName;
  const platform = urlChannelId in CHANNEL_META ? urlChannelId : 'google_ads';
  const claimed = Math.round(meta.verifiedRevenue * 1.12);
  const discPct = ((meta.verifiedRevenue - claimed) / claimed) * 100;
  return {
    channelId: (() => {
      const map: Record<string, string> = { google_ads: 'ch_google_ads', meta: 'ch_meta_ads', tiktok: 'ch_tiktok_ads', linkedin: 'ch_linkedin_ads', pinterest: 'ch_pinterest_ads' };
      return map[urlChannelId] ?? 'ch_google_ads';
    })(),
    channelName,
    platform,
    spend: meta.spend,
    spendFormatted: formatCurrency(meta.spend),
    spendTrend: {
      direction: 'up' as const,
      valuePct: 5.2,
      formattedValue: '\u2191 5.2%',
      comparisonPeriod: 'vs. previous 30 days',
    },
    verifiedRevenue: meta.verifiedRevenue,
    verifiedRevenueFormatted: formatCurrency(meta.verifiedRevenue),
    claimedRevenue: claimed,
    claimedRevenueFormatted: formatCurrency(claimed),
    discrepancyPct: Math.round(discPct * 10) / 10,
    verificationStatus: 'verified' as const,
    attributionWeight: meta.attributionWeight,
    attributionMethod: 'bayesian' as const,
    roas: {
      estimate: meta.roasEst,
      formattedEstimate: meta.roasEst.toFixed(2),
      lower: meta.roasLow,
      formattedLower: meta.roasLow.toFixed(2),
      upper: meta.roasUp,
      formattedUpper: meta.roasUp.toFixed(2),
      bucket: 'narrow' as const,
      rangeLabel: '80% credible interval',
    },
    saturation: {
      headroomPct: 18,
      saturationPoint: Math.round(meta.spend / 0.82 * 1.18),
      currentUtilization: 0.82,
      headroomFormatted: formatCurrency(Math.round(meta.spend * 0.18 / 0.82)) + ' (18%)',
    },
  };
}

/** Returns mock data for the given channel (URL param: google_ads | meta | tiktok | linkedin | pinterest). Defaults to Google Ads. */
export function getChannelData(urlChannelId: string | undefined) {
  const channelId = urlChannelId && urlChannelId in CHANNEL_META ? urlChannelId : 'google_ads';
  return {
    channelAttribution: buildChannelAttribution(channelId),
    modelComparison,
    timeSeriesData,
    campaigns,
    sparklines,
  };
}

export const channelAttribution = buildChannelAttribution('google_ads');

export const modelComparison = {
  agreementScore: 0.94,
  divergenceFlag: false,
  models: [
    { method: 'bayesian', isActive: true, roas: 3.20, roasFormatted: '3.20', credibleInterval: { lower: '2.80', upper: '3.60', bucket: 'narrow' as const }, attributionWeight: 0.342, weightFormatted: '34.2%', agreementWithBayesian: null as number | null, agreementLabel: null as string | null },
    { method: 'linear', displayName: 'Linear', isActive: false, roas: 2.80, roasFormatted: '2.80', credibleInterval: null, attributionWeight: 0.03, weightFormatted: '0.03', agreementWithBayesian: 0.94, agreementLabel: 'Models agree' },
    { method: 'bayesian_det', displayName: 'Bayesian', isActive: false, roas: 3.20, roasFormatted: '3.20', credibleInterval: null, attributionWeight: 0.94, weightFormatted: '0.94', agreementWithBayesian: 0.94, agreementLabel: 'Models agree' },
    { method: 'linear_2', displayName: 'Linear', isActive: false, roas: 4.70, roasFormatted: '4.70', credibleInterval: null, attributionWeight: 0.03, weightFormatted: '0.03', agreementWithBayesian: 0.85, agreementLabel: 'Models agree' },
    { method: 'time_decay', displayName: 'Time Decay', isActive: false, roas: 0.95, roasFormatted: '0.95', credibleInterval: null, attributionWeight: 0.02, weightFormatted: '0.02', agreementWithBayesian: 0.91, agreementLabel: 'Models agree' },
    { method: 'position_based', displayName: 'Position Based', isActive: false, roas: 2.00, roasFormatted: '2.00', credibleInterval: null, attributionWeight: 0.03, weightFormatted: '0.03', agreementWithBayesian: 0.88, agreementLabel: 'Models agree' },
  ],
};

const generateTimeSeries = () => {
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'];
  const data: any[] = [];
  const pointsPerMonth = 4;
  for (let m = 0; m < months.length; m++) {
    for (let p = 0; p < pointsPerMonth; p++) {
      const idx = m * pointsPerMonth + p;
      const trend = idx * 0.008;
      const noise = (Math.sin(idx * 2.7183) * 0.5) * 0.1;
      const est = +(2.85 + trend + noise).toFixed(2);
      const halfSpread = 0.18 + (Math.sin(idx * 1.618) * 0.5 + 0.5) * 0.05;
      const day = p * 7 + 1;
      data.push({
        date: `2025-${String(m + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`,
        month: months[m],
        bayesian: { estimate: est, lower: +(est - halfSpread).toFixed(2), upper: +(est + halfSpread).toFixed(2) },
        deterministic: +(est * 0.97 + (Math.sin(idx * 3.14) * 0.5) * 0.08).toFixed(2),
      });
    }
  }
  return data;
};

export const timeSeriesData = generateTimeSeries();

export const campaigns = [
  { campaignId: 'c1', campaignName: 'Brand Search', spend: 22400, spendFormatted: '$22,400', verifiedRevenue: 71680, verifiedRevenueFormatted: '$71,680', discrepancyPct: -10320, discrepancyStatus: 'flagged' as const, roas: { estimate: 3.20, formattedEstimate: '3.20', lower: 2.80, formattedLower: '2.80', upper: 3.60, formattedUpper: '3.60', bucket: 'narrow' as const }, attributionWeight: 0.03, weightFormatted: '0.03', confidenceBucket: 'narrow' as const, status: 'active' },
  { campaignId: 'c2', campaignName: 'Non-Brand Search', spend: 22400, spendFormatted: '$22,400', verifiedRevenue: 71680, verifiedRevenueFormatted: '$71,680', discrepancyPct: -10320, discrepancyStatus: 'flagged' as const, roas: { estimate: 3.70, formattedEstimate: '3.70', lower: 2.80, formattedLower: '2.80', upper: 4.60, formattedUpper: '4.60', bucket: 'narrow' as const }, attributionWeight: 0.94, weightFormatted: '0.94', confidenceBucket: 'narrow' as const, status: 'active' },
  { campaignId: 'c3', campaignName: 'Google Ads', spend: 22400, spendFormatted: '$22,400', verifiedRevenue: 71680, verifiedRevenueFormatted: '$71,680', discrepancyPct: 0.006, discrepancyStatus: 'accurate' as const, roas: { estimate: 3.20, formattedEstimate: '3.20', lower: 2.80, formattedLower: '2.80', upper: 3.60, formattedUpper: '3.60', bucket: 'narrow' as const }, attributionWeight: 0.05, weightFormatted: '0.05', confidenceBucket: 'narrow' as const, status: 'active' },
  { campaignId: 'c4', campaignName: 'Google Ads', spend: 22400, spendFormatted: '$22,400', verifiedRevenue: 71680, verifiedRevenueFormatted: '$71,680', discrepancyPct: 36.45, discrepancyStatus: 'accurate' as const, roas: { estimate: 3.20, formattedEstimate: '3.20', lower: 2.80, formattedLower: '2.80', upper: 3.60, formattedUpper: '3.60', bucket: 'narrow' as const }, attributionWeight: 0.94, weightFormatted: '0.94', confidenceBucket: 'narrow' as const, status: 'active' },
  { campaignId: 'c5', campaignName: 'Google Ads', spend: 22400, spendFormatted: '$22,400', verifiedRevenue: 71680, verifiedRevenueFormatted: '$71,680', discrepancyPct: 24.515, discrepancyStatus: 'accurate' as const, roas: { estimate: 1.20, formattedEstimate: '1.20', lower: 0.80, formattedLower: '0.80', upper: 1.60, formattedUpper: '1.60', bucket: 'medium' as const }, attributionWeight: 0.92, weightFormatted: '0.92', confidenceBucket: 'medium' as const, status: 'active' },
  { campaignId: 'c6', campaignName: 'Channel', spend: 22400, spendFormatted: '$22,400', verifiedRevenue: 71680, verifiedRevenueFormatted: '$71,680', discrepancyPct: -12.6, discrepancyStatus: 'flagged' as const, roas: { estimate: 3.20, formattedEstimate: '3.20', lower: 2.80, formattedLower: '2.80', upper: 3.60, formattedUpper: '3.60', bucket: 'narrow' as const }, attributionWeight: 0.03, weightFormatted: '0.03', confidenceBucket: 'narrow' as const, status: 'active' },
];
