export const BENCHMARKS_COPY = {
  title: 'Benchmark Intelligence',
  subtitle:
    'Market and context signals with source authority, coverage, suppression, comparability, and actionability.',
  boundaryBanner:
    'Benchmarks provide context. They do not create verified revenue, prove causal lift, or authorize action.',
  filters: {
    heading: 'Filters',
    dateRange: 'Date range',
    channel: 'Channel',
    platform: 'Platform',
    commerceSource: 'Commerce source',
    evidenceClass: 'Evidence class',
    coverageClass: 'Coverage class',
    actionability: 'Actionability',
    clearFilters: 'Clear filters',
    allChannels: 'All channels',
    allPlatforms: 'All platforms',
    allCommerceSources: 'All commerce sources',
    allEvidenceClasses: 'All evidence classes',
    allCoverageClasses: 'All coverage classes',
    allActionability: 'All actionability',
  },
  table: {
    sectionTitle: 'Benchmark results',
    envelopeCount: (count: number) => `${count} benchmark envelope${count === 1 ? '' : 's'}`,
    lastUpdated: (minutes: number) => `Last updated ${minutes} min ago`,
    caption:
      'Benchmark intelligence results. Benchmarks provide context and do not create verified revenue or action authority.',
    benchmarkName: 'Benchmark name',
    rawBenchmark: 'Raw benchmark',
    decisionSafeBenchmark: 'Decision-safe benchmark',
    evidenceClass: 'Evidence class',
    coverageClass: 'Coverage class',
    suppressionReason: 'Suppression reason',
    comparableToPrevious: 'Comparable to previous',
    actionability: 'Actionability',
    empty: 'No defensible benchmark exists for this segment yet.',
    filteredEmpty: 'No benchmarks match these filters.',
    updating: 'Updating benchmark results…',
    loadingProgress: 'Loading benchmark intelligence…',
    notAvailable: 'N/A',
    unavailableSegmentCopy: 'No defensible benchmark is available for this segment.',
    comparableCheckmark: 'Comparable to previous period',
    estimatorTransitionBadge: 'Estimator Transition',
    estimatorTransitionTooltip: 'Benchmark source changed. This is not displayed as market movement.',
    historicalPriorDisclaimer: 'Historical prior. Not live Skeldir empirical evidence.',
    decisionSafePrivacyBlend: 'Privacy blend applied to cross-tenant cohort.',
    decisionSafeTransitionAdjustment:
      'Adjusted after estimator transition — not comparable to prior rolled-up value.',
    decisionSafeRollupAdjustment: (level: string) => `Rolled-up adjustment at ${level}.`,
    rollupTooltip: (level: string) => `Rolled up to ${level}.`,
    rollupTooltipDefault: 'Rolled up to Platform-Vertical level.',
  },
  pagination: {
    range: (start: number, end: number, total: number) => `${start}–${end} of ${total}`,
  },
  drawer: {
    title: 'Benchmark source details',
    loading: 'Loading benchmark source details…',
    error: 'Benchmark source details failed to load. No financial truth was changed.',
    close: 'Close benchmark source details',
    relatedTrustEnvelope: 'Related TrustEnvelope',
    relatedAudit: 'Related audit',
    sourceTransitionCopy: 'Benchmark source changed. This is not displayed as market movement.',
  },
  comparability: {
    sourceTransitionInline:
      'Source transition — not comparable to prior value: Estimator transition',
  },
  suppression: {
    defaultTooltip: 'Benchmark value withheld for privacy or safety.',
    tooltips: {
      low_k:
        'Exact bucket suppressed: cohort size below k-anonymity threshold to prevent tenant re-identification.',
      dominance_risk:
        'Exact bucket suppressed: dominance risk prevents safe cross-tenant release.',
      policy_excluded: 'Benchmark suppressed by tenant policy boundary.',
      sparse_data: 'Insufficient observations to release a defensible benchmark.',
    },
  },
  budgetSimulation: {
    blockedEstimatorTransition:
      'This benchmark segment is blocked from budget simulation until the estimator stabilizes after a source transition.',
  },
} as const;
