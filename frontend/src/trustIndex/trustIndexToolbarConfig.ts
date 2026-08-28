import type { TrustIndexFilters } from './trustIndexClient';
import { TRUST_INDEX_DEFAULT_SORT_KEY } from './trustIndexEnvelopeDisplay';

export const TRUST_INDEX_SORT_PRESETS = [
  {
    id: 'priority_default',
    label: 'Priority (policy → discrepancy)',
    sortKey: TRUST_INDEX_DEFAULT_SORT_KEY,
    sortDirection: 'desc',
  },
  {
    id: 'newest_claim',
    label: 'Newest claim time',
    sortKey: 'claimTime',
    sortDirection: 'desc',
  },
  {
    id: 'oldest_claim',
    label: 'Oldest claim time',
    sortKey: 'claimTime',
    sortDirection: 'asc',
  },
  {
    id: 'largest_discrepancy',
    label: 'Largest discrepancy',
    sortKey: 'discrepancyRateBps',
    sortDirection: 'desc',
  },
] as const;

export type TrustIndexSortPresetId = (typeof TRUST_INDEX_SORT_PRESETS)[number]['id'];

export function resolveTrustIndexSortPresetId(filters: TrustIndexFilters): TrustIndexSortPresetId {
  const sortKey = filters.sortKey ?? TRUST_INDEX_DEFAULT_SORT_KEY;
  const sortDirection = filters.sortDirection ?? 'desc';
  const match = TRUST_INDEX_SORT_PRESETS.find(
    (preset) => preset.sortKey === sortKey && preset.sortDirection === sortDirection,
  );
  return match?.id ?? 'priority_default';
}

export function applyTrustIndexSortPreset(
  presetId: TrustIndexSortPresetId,
  filters: TrustIndexFilters,
): TrustIndexFilters {
  const preset = TRUST_INDEX_SORT_PRESETS.find((entry) => entry.id === presetId) ?? TRUST_INDEX_SORT_PRESETS[0];
  return {
    ...filters,
    sortKey: preset.sortKey,
    sortDirection: preset.sortDirection as 'asc' | 'desc',
    offset: 0,
  };
}
