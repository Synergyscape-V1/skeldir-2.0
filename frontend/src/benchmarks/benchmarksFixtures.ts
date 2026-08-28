import type {

  BenchmarkActionability,

  BenchmarkCoverageClass,

  BenchmarkEvidenceClass,

  BenchmarkRowDTO,

} from '../ledger/types';

import { BENCHMARKS_COPY } from './copy';



function buildBenchmarkShape(row: Omit<BenchmarkRowDTO, 'benchmark'>): BenchmarkRowDTO['benchmark'] {

  if (row.evidenceClass === 'unavailable' && !row.rawBenchmark) {

    return {

      status: 'unavailable',

      reason: row.suppressionReason ?? BENCHMARKS_COPY.table.unavailableSegmentCopy,

    };

  }

  if ((row.suppressionReason || row.suppressionReasonCode) && !row.rawBenchmark) {

    return {

      status: 'suppressed',

      suppressionReason: row.suppressionReason ?? row.suppressionReasonCode,

    };

  }

  return {

    status: 'available',

    rawBenchmark: row.rawBenchmark,

    decisionSafeBenchmark: row.decisionSafeBenchmark,

    evidenceClass: row.evidenceClass,

    coverageClass: row.coverageClass,

    suppressionReason: row.suppressionReason ?? row.suppressionReasonCode,

    comparability: row.comparability,

    sourceTransition: row.sourceTransition,

    transitionReason: row.transitionReason,

  };

}



function row(

  partial: Omit<BenchmarkRowDTO, 'benchmark' | 'policyAuthority' | 'lastRefreshed'> & {

    lastRefreshed?: string;

  },

): BenchmarkRowDTO {

  const lastRefreshed = partial.lastRefreshed ?? new Date(Date.now() - 12 * 60_000).toISOString();

  const base = {

    ...partial,

    policyAuthority: 'blocked' as const,

    lastRefreshed,

  };

  return { ...base, benchmark: buildBenchmarkShape(base) };

}



/** Canonical benchmark dataset aligned with Benchmark Intelligence 8-column CRHAID. */

export const BENCHMARKS_FIXTURES: BenchmarkRowDTO[] = [

  row({

    benchmarkId: 'bench_meta_paid_social',

    benchmarkName: 'Meta Ads × Paid Social',

    segmentName: 'Meta Ads × Paid Social',

    rawBenchmark: '1.94%',

    decisionSafeBenchmark: '1.71%',

    adjustmentReason: 'Privacy blend applied to cross-tenant cohort.',

    evidenceClass: 'live_empirical',

    coverageClass: 'exact',

    comparability: 'comparable',

    sourceTransition: false,

    actionability: 'simulate',

    channelId: 'meta_paid_social',

    platformId: 'meta',

    commerceSourceId: 'shopify',

    trustEnvelopeId: 'env_bench_meta',

    auditReference: 'aud_bench_meta',

  }),

  row({

    benchmarkId: 'bench_google_search',

    benchmarkName: 'Google Ads × Paid Search',

    segmentName: 'Google Ads × Paid Search',

    rawBenchmark: '14.0%',

    decisionSafeBenchmark: '14.0%',

    evidenceClass: 'live_empirical',

    coverageClass: 'broad',

    rollupLevel: 'Platform-Vertical level',

    comparability: 'comparable',

    sourceTransition: false,

    actionability: 'simulate',

    channelId: 'google_search',

    platformId: 'google',

    commerceSourceId: 'shopify',

    trustEnvelopeId: 'env_bench_google',

    auditReference: 'aud_bench_google',

  }),

  row({

    benchmarkId: 'bench_meta_paid_search_transition',

    benchmarkName: 'Meta Ads × Paid Search × US',

    segmentName: 'Meta Ads × Paid Search × US',

    rawBenchmark: '4.0%',

    decisionSafeBenchmark: '4.0%',

    adjustmentReason: 'Adjusted after estimator transition — not comparable to prior rolled-up value.',

    evidenceClass: 'live_empirical',

    coverageClass: 'exact',

    comparability: 'source_changed',

    sourceTransition: true,

    transitionReason: 'Estimator transition from broad rollup to exact bucket',

    actionability: 'simulate',

    channelId: 'meta_paid_search_us',

    platformId: 'meta',

    commerceSourceId: 'shopify',

    trustEnvelopeId: 'env_bench_meta_us',

    auditReference: 'aud_bench_meta_us',

  }),

  row({

    benchmarkId: 'bench_youtube',

    benchmarkName: 'Google Ads × YouTube Prospecting',

    segmentName: 'Google Ads × YouTube Prospecting',

    rawBenchmark: '1.28%',

    decisionSafeBenchmark: '1.28%',

    evidenceClass: 'live_empirical',

    coverageClass: 'exact',

    comparability: 'comparable',

    sourceTransition: false,

    actionability: 'simulate',

    channelId: 'youtube',

    platformId: 'google',

    commerceSourceId: 'stripe',

    trustEnvelopeId: 'env_bench_youtube',

    auditReference: 'aud_bench_youtube',

  }),

  row({

    benchmarkId: 'bench_affiliate',

    benchmarkName: 'Meta Ads × Affiliate',

    segmentName: 'Meta Ads × Affiliate',

    evidenceClass: 'tenant_longitudinal',

    coverageClass: 'tenant_only',

    suppressionReasonCode: 'policy_excluded',

    suppressionReason: 'policy_excluded',

    comparability: 'not_comparable',

    sourceTransition: false,

    actionability: 'blocked',

    channelId: 'affiliate',

    platformId: 'meta',

    commerceSourceId: 'shopify',

    trustEnvelopeId: 'env_bench_affiliate',

    auditReference: 'aud_bench_affiliate',

  }),

  row({

    benchmarkId: 'bench_tiktok',

    benchmarkName: 'TikTok Ads × TikTok Shop',

    segmentName: 'TikTok Ads × TikTok Shop',

    rawBenchmark: '2.4%',

    decisionSafeBenchmark: '2.1%',

    adjustmentReason: 'Privacy blend applied to cross-tenant cohort.',

    evidenceClass: 'live_empirical',

    coverageClass: 'broad',

    rollupLevel: 'Platform-Commerce level',

    comparability: 'comparable',

    sourceTransition: false,

    actionability: 'observe_only_until_stable',

    channelId: 'tiktok_shop',

    platformId: 'tiktok',

    commerceSourceId: 'shopify',

    trustEnvelopeId: 'env_bench_tiktok',

    auditReference: 'aud_bench_tiktok',

  }),

  row({

    benchmarkId: 'bench_email',

    benchmarkName: 'Email × Lifecycle',

    segmentName: 'Email × Lifecycle',

    rawBenchmark: '18.2%',

    decisionSafeBenchmark: '17.9%',

    evidenceClass: 'tenant_longitudinal',

    coverageClass: 'tenant_only',

    comparability: 'comparable',

    sourceTransition: false,

    actionability: 'observe_only_until_stable',

    channelId: 'email',

    platformId: 'email',

    commerceSourceId: 'shopify',

    trustEnvelopeId: 'env_bench_email',

    auditReference: 'aud_bench_email',

  }),

  row({

    benchmarkId: 'bench_amazon',

    benchmarkName: 'Amazon Ads × Sponsored Products',

    segmentName: 'Amazon Ads × Sponsored Products',

    evidenceClass: 'historical_prior',

    coverageClass: 'prior',

    comparability: 'unavailable',

    sourceTransition: false,

    actionability: 'blocked',

    channelId: 'amazon',

    platformId: 'amazon',

    commerceSourceId: 'stripe',

    trustEnvelopeId: 'env_bench_amazon',

    auditReference: 'aud_bench_amazon',

  }),

  row({

    benchmarkId: 'bench_influencer',

    benchmarkName: 'Meta Ads × Influencer Partnerships',

    segmentName: 'Meta Ads × Influencer Partnerships',

    rawBenchmark: '8.6%',

    decisionSafeBenchmark: '8.2%',

    evidenceClass: 'live_empirical',

    coverageClass: 'exact',

    comparability: 'comparable',

    sourceTransition: false,

    actionability: 'simulate',

    channelId: 'influencer',

    platformId: 'meta',

    commerceSourceId: 'stripe',

    trustEnvelopeId: 'env_bench_influencer',

    auditReference: 'aud_bench_influencer',

  }),

  row({

    benchmarkId: 'bench_linkedin',

    benchmarkName: 'LinkedIn Ads × B2B Lead Gen',

    segmentName: 'LinkedIn Ads × B2B Lead Gen',

    rawBenchmark: '9.8%',

    decisionSafeBenchmark: '10.1%',

    evidenceClass: 'tenant_longitudinal',

    coverageClass: 'tenant_only',

    suppressionReasonCode: 'sparse_data',

    suppressionReason: 'sparse_data',

    comparability: 'comparable',

    sourceTransition: false,

    actionability: 'observe_only_until_stable',

    channelId: 'linkedin',

    platformId: 'linkedin',

    commerceSourceId: 'shopify',

    trustEnvelopeId: 'env_bench_linkedin',

    auditReference: 'aud_bench_linkedin',

  }),

  row({

    benchmarkId: 'bench_pinterest',

    benchmarkName: 'Meta Ads × Pinterest Commerce',

    segmentName: 'Meta Ads × Pinterest Commerce',

    rawBenchmark: '6.2%',

    decisionSafeBenchmark: '5.5%',

    evidenceClass: 'live_empirical',

    coverageClass: 'exact',

    comparability: 'comparable',

    sourceTransition: false,

    actionability: 'simulate',

    channelId: 'pinterest',

    platformId: 'meta',

    commerceSourceId: 'shopify',

    trustEnvelopeId: 'env_bench_pinterest',

    auditReference: 'aud_bench_pinterest',

  }),

  row({

    benchmarkId: 'bench_snapchat',

    benchmarkName: 'TikTok Ads × Snapchat Swipe',

    segmentName: 'TikTok Ads × Snapchat Swipe',

    evidenceClass: 'live_empirical',

    coverageClass: 'insufficient',

    suppressionReasonCode: 'low_k',

    suppressionReason: 'low_k',

    comparability: 'unavailable',

    sourceTransition: false,

    actionability: 'blocked',

    channelId: 'snapchat',

    platformId: 'tiktok',

    commerceSourceId: 'stripe',

    trustEnvelopeId: 'env_bench_snapchat',

    auditReference: 'aud_bench_snapchat',

  }),

  row({

    benchmarkId: 'bench_podcast',

    benchmarkName: 'Email × Podcast Sponsorships',

    segmentName: 'Email × Podcast Sponsorships',

    evidenceClass: 'public_prior',

    coverageClass: 'prior',

    comparability: 'unavailable',

    sourceTransition: false,

    actionability: 'blocked',

    channelId: 'podcast',

    platformId: 'email',

    commerceSourceId: 'stripe',

    trustEnvelopeId: 'env_bench_podcast',

    auditReference: 'aud_bench_podcast',

  }),

  row({

    benchmarkId: 'bench_reddit',

    benchmarkName: 'Google Ads × Reddit CPC',

    segmentName: 'Google Ads × Reddit CPC',

    rawBenchmark: '3.1%',

    decisionSafeBenchmark: '3.1%',

    evidenceClass: 'live_empirical',

    coverageClass: 'exact',

    comparability: 'source_changed',

    sourceTransition: true,

    transitionReason: 'Estimator transition',

    actionability: 'simulate',

    channelId: 'reddit',

    platformId: 'google',

    commerceSourceId: 'shopify',

    trustEnvelopeId: 'env_bench_reddit',

    auditReference: 'aud_bench_reddit',

  }),

  row({

    benchmarkId: 'bench_display',

    benchmarkName: 'Google Ads × Programmatic Display',

    segmentName: 'Google Ads × Programmatic Display',

    rawBenchmark: '7.2%',

    decisionSafeBenchmark: '6.8%',

    evidenceClass: 'tenant_longitudinal',

    coverageClass: 'broad',

    rollupLevel: 'Platform-Vertical level',

    comparability: 'comparable',

    sourceTransition: false,

    actionability: 'observe_only_until_stable',

    channelId: 'display',

    platformId: 'google',

    commerceSourceId: 'stripe',

    trustEnvelopeId: 'env_bench_display',

    auditReference: 'aud_bench_display',

  }),

  row({

    benchmarkId: 'bench_sms',

    benchmarkName: 'Email × SMS Click Rate',

    segmentName: 'Email × SMS Click Rate',

    rawBenchmark: '4.8%',

    decisionSafeBenchmark: '4.5%',

    evidenceClass: 'live_empirical',

    coverageClass: 'exact',

    comparability: 'comparable',

    sourceTransition: false,

    actionability: 'simulate',

    channelId: 'sms',

    platformId: 'email',

    commerceSourceId: 'shopify',

    trustEnvelopeId: 'env_bench_sms',

    auditReference: 'aud_bench_sms',

  }),

  row({

    benchmarkId: 'bench_ooh',

    benchmarkName: 'Meta Ads × Out-of-home Lift',

    segmentName: 'Meta Ads × Out-of-home Lift',

    evidenceClass: 'unavailable',

    coverageClass: 'insufficient',

    comparability: 'unavailable',

    sourceTransition: false,

    actionability: 'blocked',

    channelId: 'ooh',

    platformId: 'meta',

    commerceSourceId: 'stripe',

    trustEnvelopeId: 'env_bench_ooh',

    auditReference: 'aud_bench_ooh',

  }),

  row({

    benchmarkId: 'bench_dominance',

    benchmarkName: 'Meta Ads × Creator Commerce',

    segmentName: 'Meta Ads × Creator Commerce',

    evidenceClass: 'live_empirical',

    coverageClass: 'insufficient',

    suppressionReasonCode: 'dominance_risk',

    suppressionReason: 'dominance_risk',

    comparability: 'unavailable',

    sourceTransition: false,

    actionability: 'blocked',

    channelId: 'creator_commerce',

    platformId: 'meta',

    commerceSourceId: 'shopify',

    trustEnvelopeId: 'env_bench_dominance',

    auditReference: 'aud_bench_dominance',

  }),

];



export const BENCHMARK_DEFAULT_DATE_FROM = '2026-04-01';

export const BENCHMARK_DEFAULT_DATE_TO = '2026-06-30';



export const BENCHMARK_CHANNEL_OPTIONS = [

  { id: 'meta_paid_social', label: 'Meta Paid Social' },

  { id: 'google_search', label: 'Google Search' },

  { id: 'youtube', label: 'YouTube Prospecting' },

  { id: 'affiliate', label: 'Affiliate' },

  { id: 'tiktok_shop', label: 'TikTok Shop' },

  { id: 'email', label: 'Email' },

  { id: 'amazon', label: 'Amazon Sponsored Products' },

  { id: 'influencer', label: 'Influencer Partnerships' },

] as const;



export const BENCHMARK_PLATFORM_OPTIONS = [

  { id: 'meta', label: 'Meta' },

  { id: 'google', label: 'Google' },

  { id: 'email', label: 'Email' },

  { id: 'tiktok', label: 'TikTok' },

  { id: 'linkedin', label: 'LinkedIn' },

  { id: 'amazon', label: 'Amazon' },

] as const;



export const BENCHMARK_COMMERCE_OPTIONS = [

  { id: 'shopify', label: 'Shopify' },

  { id: 'stripe', label: 'Stripe' },

] as const;



export const BENCHMARK_EVIDENCE_OPTIONS: Array<{ id: BenchmarkEvidenceClass; label: string }> = [

  { id: 'live_empirical', label: 'Live Skeldir Empirical' },

  { id: 'tenant_longitudinal', label: 'Tenant-Longitudinal' },

  { id: 'historical_prior', label: 'Historical Prior' },

  { id: 'public_prior', label: 'Public Prior' },

  { id: 'unavailable', label: 'Unavailable' },

];



export const BENCHMARK_COVERAGE_OPTIONS: Array<{ id: BenchmarkCoverageClass; label: string }> = [

  { id: 'exact', label: 'exact' },

  { id: 'broad', label: 'broad' },

  { id: 'tenant_only', label: 'tenant_only' },

  { id: 'prior', label: 'prior' },

  { id: 'insufficient', label: 'insufficient' },

];



export const BENCHMARK_ACTIONABILITY_OPTIONS: Array<{ id: BenchmarkActionability; label: string }> = [

  { id: 'simulate', label: 'simulate' },

  { id: 'observe_only_until_stable', label: 'observe_only_until_stable' },

  { id: 'blocked', label: 'blocked' },

];


