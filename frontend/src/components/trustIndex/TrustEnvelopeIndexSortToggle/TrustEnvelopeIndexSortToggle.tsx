import { TRUST_ENVELOPE_INDEX_COPY } from '../../../trustIndex/copy';
import type { TrustIndexFilters } from '../../../trustIndex/trustIndexClient';
import {
  applyTrustIndexSortPreset,
  resolveTrustIndexSortPresetId,
  TRUST_INDEX_SORT_PRESETS,
  type TrustIndexSortPresetId,
} from '../../../trustIndex/trustIndexToolbarConfig';
import shared from '../../../styles/shared.module.css';
import styles from './TrustEnvelopeIndexSortToggle.module.css';

export interface TrustEnvelopeIndexSortToggleProps {
  filters: TrustIndexFilters;
  onFilterChange: (next: TrustIndexFilters) => void;
  loading?: boolean;
  disabled?: boolean;
}

export function TrustEnvelopeIndexSortToggle({
  filters,
  onFilterChange,
  loading = false,
  disabled: readOnly = false,
}: TrustEnvelopeIndexSortToggleProps) {
  const disabled = loading || readOnly;
  const sortPresetId = resolveTrustIndexSortPresetId(filters);

  const handleSortChange = (presetId: TrustIndexSortPresetId) => {
    onFilterChange(applyTrustIndexSortPreset(presetId, filters));
  };

  return (
    <div
      className={styles.sortToggle}
      role="radiogroup"
      aria-label={`${TRUST_ENVELOPE_INDEX_COPY.toolbar.sortLabel} TrustEnvelopes`}
      data-trust-index-sort
    >
      {TRUST_INDEX_SORT_PRESETS.map((preset) => (
        <button
          key={preset.id}
          type="button"
          role="radio"
          aria-checked={sortPresetId === preset.id}
          className={[
            styles.sortToggleButton,
            sortPresetId === preset.id ? styles.sortToggleButtonActive : '',
            shared.focusVisible,
          ]
            .filter(Boolean)
            .join(' ')}
          onClick={() => handleSortChange(preset.id)}
          disabled={disabled}
          data-trust-index-sort-option={preset.id}
        >
          {preset.label}
        </button>
      ))}
    </div>
  );
}
