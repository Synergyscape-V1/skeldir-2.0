import type { TrustIndexFilters } from '../../../trustIndex/trustIndexClient';
import { TRUST_ENVELOPE_INDEX_COPY } from '../../../trustIndex/copy';
import {
  ALLOWED_TRUST_CONFIDENCE_AVAILABILITY,
  ALLOWED_TRUST_VERIFICATION_STATUSES,
} from '../../../trustIndex/trustIndexQueryState';
import {
  TRUST_INDEX_CONFIDENCE_AVAILABILITY_LABELS,
  TRUST_INDEX_DISCREPANCY_FILTER_OPTIONS,
  TRUST_INDEX_POLICY_LABELS,
  TRUST_INDEX_VERIFICATION_LABELS,
  trustIndexDiscrepancyFilterLabel,
} from '../../../trustIndex/trustIndexFilterConfig';
import { POLICY_AUTHORITY_STATES } from '../../../lib/types';
import { hasActiveTrustIndexFilters } from '../../../trustIndex/trustIndexFilterMatching';
import shared from '../../../styles/shared.module.css';
import styles from './TrustEnvelopeIndexFilters.module.css';

export interface TrustEnvelopeIndexFiltersProps {
  filters: TrustIndexFilters;
  onChange: (filters: TrustIndexFilters) => void;
  onClearAll?: () => void;
  disabled?: boolean;
}

export function TrustEnvelopeIndexFilters({
  filters,
  onChange,
  onClearAll,
  disabled = false,
}: TrustEnvelopeIndexFiltersProps) {
  const showClear = hasActiveTrustIndexFilters(filters);

  const update = (patch: Partial<TrustIndexFilters>) => {
    onChange({ ...filters, ...patch, offset: 0 });
  };

  return (
    <section className={styles.panel} data-trust-index-filters aria-label="TrustEnvelope index filters">
      <div className={styles.primaryRow}>
        <label className={styles.field}>
          <span className={styles.fieldLabel}>{TRUST_ENVELOPE_INDEX_COPY.filters.verificationStatus}</span>
          <select
            className={[styles.control, shared.focusVisible].join(' ')}
            value={filters.verificationStatus ?? ''}
            disabled={disabled}
            onChange={(e) =>
              update({
                verificationStatus: (e.target.value || undefined) as TrustIndexFilters['verificationStatus'],
              })
            }
            aria-label={TRUST_ENVELOPE_INDEX_COPY.filters.verificationStatus}
          >
            <option value="">All</option>
            {ALLOWED_TRUST_VERIFICATION_STATUSES.map((value) => (
              <option key={value} value={value}>
                {TRUST_INDEX_VERIFICATION_LABELS[value]}
              </option>
            ))}
          </select>
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>{TRUST_ENVELOPE_INDEX_COPY.filters.discrepancyClass}</span>
          <select
            className={[styles.control, shared.focusVisible].join(' ')}
            value={filters.discrepancyClass ?? ''}
            disabled={disabled}
            onChange={(e) =>
              update({ discrepancyClass: (e.target.value || undefined) as TrustIndexFilters['discrepancyClass'] })
            }
            aria-label={TRUST_ENVELOPE_INDEX_COPY.filters.discrepancyClass}
          >
            <option value="">All</option>
            {TRUST_INDEX_DISCREPANCY_FILTER_OPTIONS.map((value) => (
              <option key={value} value={value}>
                {trustIndexDiscrepancyFilterLabel(value)}
              </option>
            ))}
          </select>
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>{TRUST_ENVELOPE_INDEX_COPY.filters.policyAuthority}</span>
          <select
            className={[styles.control, shared.focusVisible].join(' ')}
            value={filters.policyAuthority ?? ''}
            disabled={disabled}
            onChange={(e) =>
              update({ policyAuthority: (e.target.value || undefined) as TrustIndexFilters['policyAuthority'] })
            }
            aria-label={TRUST_ENVELOPE_INDEX_COPY.filters.policyAuthority}
          >
            <option value="">All</option>
            {POLICY_AUTHORITY_STATES.map((value) => (
              <option key={value} value={value}>
                {TRUST_INDEX_POLICY_LABELS[value]}
              </option>
            ))}
          </select>
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>{TRUST_ENVELOPE_INDEX_COPY.filters.confidenceAvailability}</span>
          <select
            className={[styles.control, shared.focusVisible].join(' ')}
            value={filters.confidenceAvailability ?? ''}
            disabled={disabled}
            onChange={(e) =>
              update({
                confidenceAvailability: (e.target.value || undefined) as TrustIndexFilters['confidenceAvailability'],
              })
            }
            aria-label={TRUST_ENVELOPE_INDEX_COPY.filters.confidenceAvailability}
          >
            <option value="">All</option>
            {ALLOWED_TRUST_CONFIDENCE_AVAILABILITY.map((value) => (
              <option key={value} value={value}>
                {TRUST_INDEX_CONFIDENCE_AVAILABILITY_LABELS[value]}
              </option>
            ))}
          </select>
        </label>

        {showClear && onClearAll ? (
          <button
            type="button"
            className={[styles.clearFilters, shared.focusVisible].join(' ')}
            disabled={disabled}
            onClick={onClearAll}
          >
            {TRUST_ENVELOPE_INDEX_COPY.filters.clearFilters}
          </button>
        ) : null}
      </div>
    </section>
  );
}
