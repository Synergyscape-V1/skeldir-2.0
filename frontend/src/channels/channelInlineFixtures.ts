export interface ChannelInlineTrendPoint {
  period: string;
  verifiedRevenueMinor: bigint;
}

export interface ChannelInlineCampaignRow {
  campaignId: string;
  campaignName: string;
  verifiedRevenueMinor: bigint;
  shareBps: number;
}

export interface ChannelInlineExpansionFixture {
  trend: ChannelInlineTrendPoint[];
  campaigns: ChannelInlineCampaignRow[];
}

const DEFAULT_TREND: ChannelInlineTrendPoint[] = [
  { period: 'W1', verifiedRevenueMinor: 6_200_000n },
  { period: 'W2', verifiedRevenueMinor: 7_100_000n },
  { period: 'W3', verifiedRevenueMinor: 6_850_000n },
  { period: 'W4', verifiedRevenueMinor: 8_040_000n },
];

/**
 * Executive-facing expansion fixtures. Campaigns are the budget-reallocation lever (Audit 1).
 * No attribution-model rows, confidence intervals, or TrustEnvelope objects.
 */
export function getChannelInlineExpansionFixture(channelId: string): ChannelInlineExpansionFixture {
  if (channelId.includes('paid_social') || channelId.includes('meta')) {
    return {
      trend: [
        { period: 'W1', verifiedRevenueMinor: 5_400_000n },
        { period: 'W2', verifiedRevenueMinor: 6_100_000n },
        { period: 'W3', verifiedRevenueMinor: 5_900_000n },
        { period: 'W4', verifiedRevenueMinor: 8_214_000n },
      ],
      campaigns: [
        {
          campaignId: 'cmp_meta_prospecting',
          campaignName: 'Prospecting — Broad',
          verifiedRevenueMinor: 11_200_000n,
          shareBps: 4370,
        },
        {
          campaignId: 'cmp_meta_retarget',
          campaignName: 'Retargeting — Cart',
          verifiedRevenueMinor: 8_100_000n,
          shareBps: 3160,
        },
        {
          campaignId: 'cmp_meta_catalog',
          campaignName: 'Catalog Sales',
          verifiedRevenueMinor: 6_314_000n,
          shareBps: 2470,
        },
      ],
    };
  }

  if (channelId.includes('paid_search') || channelId.includes('google')) {
    return {
      trend: DEFAULT_TREND,
      campaigns: [
        {
          campaignId: 'cmp_brand',
          campaignName: 'Brand Search',
          verifiedRevenueMinor: 18_400_000n,
          shareBps: 4290,
        },
        {
          campaignId: 'cmp_nonbrand',
          campaignName: 'Non-Brand Capture',
          verifiedRevenueMinor: 14_200_000n,
          shareBps: 3310,
        },
        {
          campaignId: 'cmp_competitors',
          campaignName: 'Competitor Terms',
          verifiedRevenueMinor: 10_246_000n,
          shareBps: 2400,
        },
      ],
    };
  }

  return {
    trend: DEFAULT_TREND,
    campaigns: [
      {
        campaignId: `cmp_${channelId}_primary`,
        campaignName: 'Primary always-on',
        verifiedRevenueMinor: 9_500_000n,
        shareBps: 5200,
      },
      {
        campaignId: `cmp_${channelId}_test`,
        campaignName: 'Test / learning',
        verifiedRevenueMinor: 4_200_000n,
        shareBps: 2300,
      },
    ],
  };
}
