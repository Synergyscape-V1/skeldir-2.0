export const BUDGET_CHANNEL_OPTIONS = [
  { id: 'paid_search', label: 'Paid Search', color: 'var(--sk-color-trust-probabilistic)' },
  { id: 'paid_social', label: 'Paid Social', color: 'var(--sk-color-status-success)' },
  { id: 'affiliate', label: 'Affiliate', color: 'var(--sk-color-status-warning)' },
  { id: 'email', label: 'Email', color: 'var(--sk-color-trust-benchmark)' },
  { id: 'display', label: 'Display', color: 'var(--sk-color-status-info)' },
] as const;

export const BUDGET_DATE_RANGE_PRESETS = [
  {
    id: 'may-jun-2026',
    label: 'May 1, 2026 – Jun 30, 2026',
    start: '2026-05-01',
    end: '2026-06-30',
  },
  {
    id: 'jun-jul-2026',
    label: 'Jun 3, 2026 – Jul 3, 2026',
    start: '2026-06-03',
    end: '2026-07-03',
  },
] as const;

export const BUDGET_OBJECTIVE_OPTIONS = [
  { id: 'maximize_verified_revenue', label: 'Maximize verified revenue' },
  {
    id: 'maximize_within_constraint',
    label: 'Maximize verified revenue within spend constraint',
  },
] as const;

export const BUDGET_REVENUE_WINDOW_OPTIONS = [
  { id: 7, label: '7 days' },
  { id: 14, label: '14 days' },
  { id: 30, label: '30 days' },
  { id: 60, label: '60 days' },
  { id: 90, label: '90 days' },
] as const;

export const BUDGET_SUFFICIENCY_THRESHOLDS = {
  minimumChannels: 3,
  minimumVerifiedConversions: 300,
  fixtureVerifiedConversions: 842,
} as const;

export const BUDGET_DEFAULT_SPEND_MINOR = 12_500_000n;
export const BUDGET_DEFAULT_CURRENCY = 'USD';

export function channelLabelForId(id: string): string {
  return BUDGET_CHANNEL_OPTIONS.find((c) => c.id === id)?.label ?? id;
}

export function channelColorForId(id: string): string {
  return BUDGET_CHANNEL_OPTIONS.find((c) => c.id === id)?.color ?? 'var(--sk-color-text-muted)';
}
