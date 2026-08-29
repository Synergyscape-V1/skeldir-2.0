export const CHANNEL_INLINE_COPY = {
  reliability: {
    label: 'Data reliability',
    verified: 'Verified',
    estimated: 'Estimated',
    pending: 'Pending',
    tooltip: (state: string) => `Source reliability: ${state}`,
  },
  revenue: {
    claimed: 'Claimed',
    verified: 'Verified',
    difference: 'Difference',
    verifiedMeta: 'Ledger-authoritative total',
    claimedMeta: 'Platform-reported claim',
    claimedMetaCrossed: 'Conflicts with verified ledger',
  },
  attribution: {
    modelLine: 'Data-driven attribution',
  },
  confidence: {
    verifiedExplain: 'Deterministic commerce evidence supports this channel total.',
    estimatedExplain: 'More transactions needed for a full statistical range.',
    pendingExplain: 'Reliability assessment is still resolving for this channel.',
  },
  benchmark: {
    unavailable: 'No defensible market comparison yet',
    prefix: 'vs. Market',
  },
  trend: {
    sectionLabel: '30-day verified trend',
    empty: 'Not enough history to chart.',
    error:
      'Verified trend unavailable. Channel totals above remain authoritative.',
    deltaFirst: 'First period in range',
    deltaFlat: 'Flat vs prior week',
    deltaFromZero: 'Up from zero prior week',
    deltaUp: (pct: string) => `+${pct} vs prior week`,
    deltaDown: (pct: string) => `−${pct} vs prior week`,
    retry: 'Retry trend',
  },
  campaigns: {
    sectionLabel: 'Top campaigns',
    empty: 'No campaign breakdown available for this channel.',
    columns: {
      name: 'Campaign',
      verified: 'Verified',
      share: 'Share',
    },
  },
  actions: {
    reviewClaims: 'Review claims',
    reviewClaimsWithCount: (count: number) =>
      count === 1 ? 'Review 1 claim' : `Review ${count} claims`,
    holdSpend: 'Hold spend',
    holdBlockedTooltip: 'Spend hold is unavailable under current policy authority.',
    holdBlockedPolicy: 'Spend changes are blocked by current policy authority.',
  },
  loading: {
    progress: 'Loading channel defense…',
  },
  error: {
    message:
      'Channel defense data unavailable. Verified ledger totals above remain authoritative.',
  },
  platformWarning: 'Platform-reported revenue is a claim source, not verified truth.',
} as const;
