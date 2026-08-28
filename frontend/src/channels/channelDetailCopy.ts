export const CHANNEL_DETAIL_COPY = {
  title: 'Channel',
  pageQuestion: 'Can I trust this channel right now?',
  metadataLine:
    'Revenue shown here is verified commerce evidence unless explicitly marked as platform-reported claim data.',
  decks: {
    hardTruthQuestion: 'What did the bank say vs. what did the platform say?',
    mathModelsQuestion: 'How did we divide credit across the customer journey?',
    maybeContextQuestion: 'What are the statistical guesses, and how do we compare to the market?',
  },
  verdict: {
    label: 'Channel verdict',
    deterministicallyVerified: 'Deterministically Verified',
    assumptionSensitive: 'Assumption-Sensitive',
    highlyContested: 'Highly Contested',
  },
  reconciliation: {
    sectionTitle: 'Claim vs commerce reconciliation',
    verifiedLabel: 'Verified revenue',
    claimedLabel: 'Platform-reported revenue',
    platformWarning: 'Platform-reported revenue is a claim source, not verified truth.',
    discrepancyLabel: 'Discrepancy class',
    exportLabel: 'Export evidence (Level 9)',
  },
  models: {
    sectionTitle: 'Attribution model comparison',
    caption:
      'Attribution model comparison table showing model, verified revenue allocated, share of verified revenue, model assumption, and agreement tier.',
    disclaimer: 'Attribution models are deterministic heuristics. They do not prove causal lift.',
    disagreementWarning:
      'Attribution models disagree. Treat channel-level allocation as assumption-sensitive.',
    columns: {
      model: 'Model',
      allocated: 'Verified revenue allocated',
      share: 'Share of verified revenue',
      assumption: 'Model assumption',
      tier: 'Agreement tier',
    },
  },
  confidence: {
    sectionTitle: 'Confidence interval',
    unavailableReason: 'Probabilistic confidence is unavailable because insufficient_data.',
    whatStillWorks:
      'Deterministic verification remains available. Confidence is unavailable.',
  },
  benchmark: {
    sectionTitle: 'Benchmark context',
    sourceTransitionWarning: 'Benchmark source changed. This is not displayed as market movement.',
  },
  supporting: {
    revenueOverTime: 'Verified revenue over time',
    relatedClaims: 'Related claims',
    relatedEnvelopes: 'Related TrustEnvelopes',
  },
  trustEnvelope: {
    loading: 'Loading trust record…',
    recommendedAction: 'Recommended action',
  },
} as const;
