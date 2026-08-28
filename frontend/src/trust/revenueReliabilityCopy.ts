import type { RevenueReliabilityState } from './revenueReliability';

export const REVENUE_RELIABILITY_COLUMN_HEADER = 'Revenue Reliability';

/** Header info tooltip — commercial risk language only; no attribution-model mechanics. */
export const REVENUE_RELIABILITY_HEADER_TOOLTIP =
  'How defensible this channel’s revenue is for budget decisions. Robust is safe to scale and defend. Fragile means treat spend increases as assumptions — not facts.';

const BADGE_LABEL: Record<RevenueReliabilityState, string> = {
  robust: 'Robust',
  mixed: 'Mixed',
  fragile: 'Fragile',
};

const BADGE_TOOLTIP: Record<RevenueReliabilityState, string> = {
  robust: 'Stable and CFO-defensible. Safe to use for budget decisions.',
  mixed: 'Some uncertainty remains. Review before increasing spend.',
  fragile:
    'Unstable for budget decisions. Do not increase spend until tracking is stronger — treat as an assumption, not a fact.',
};

export function revenueReliabilityBadgeLabel(state: RevenueReliabilityState): string {
  return BADGE_LABEL[state];
}

export function revenueReliabilityBadgeTooltip(state: RevenueReliabilityState): string {
  return BADGE_TOOLTIP[state];
}
