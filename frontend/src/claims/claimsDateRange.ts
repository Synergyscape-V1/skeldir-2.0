import type { ClaimsFilters } from './claimsClient';

export type ClaimsDateRangePreset = 'all' | 'last_7_days' | 'last_30_days' | 'last_90_days';

export const CLAIMS_DATE_RANGE_PRESETS: readonly ClaimsDateRangePreset[] = [
  'all',
  'last_7_days',
  'last_30_days',
  'last_90_days',
] as const;

export const CLAIMS_DATE_RANGE_LABELS: Record<ClaimsDateRangePreset, string> = {
  all: 'All dates',
  last_7_days: 'Last 7 days',
  last_30_days: 'Last 30 days',
  last_90_days: 'Last 90 days',
};

function utcDateOnly(date: Date): string {
  return date.toISOString().slice(0, 10);
}

export function presetToDateRange(preset: ClaimsDateRangePreset): Pick<ClaimsFilters, 'dateFrom' | 'dateTo'> {
  if (preset === 'all') {
    return { dateFrom: undefined, dateTo: undefined };
  }

  const to = new Date();
  const from = new Date(to);
  const days = preset === 'last_7_days' ? 7 : preset === 'last_30_days' ? 30 : 90;
  from.setUTCDate(from.getUTCDate() - (days - 1));

  return {
    dateFrom: utcDateOnly(from),
    dateTo: utcDateOnly(to),
  };
}

export function resolveDateRangePreset(
  dateFrom?: string,
  dateTo?: string,
): ClaimsDateRangePreset | 'custom' {
  if (!dateFrom && !dateTo) return 'all';
  if (!dateFrom || !dateTo) return 'custom';

  for (const preset of ['last_7_days', 'last_30_days', 'last_90_days'] as const) {
    const range = presetToDateRange(preset);
    if (range.dateFrom === dateFrom && range.dateTo === dateTo) {
      return preset;
    }
  }

  return 'custom';
}

export function dateRangeChipLabel(dateFrom?: string, dateTo?: string): string | undefined {
  const preset = resolveDateRangePreset(dateFrom, dateTo);
  if (preset === 'all') return undefined;
  if (preset !== 'custom') return CLAIMS_DATE_RANGE_LABELS[preset];
  if (dateFrom && dateTo) return `${dateFrom} – ${dateTo}`;
  if (dateFrom) return `From ${dateFrom}`;
  if (dateTo) return `Until ${dateTo}`;
  return undefined;
}
