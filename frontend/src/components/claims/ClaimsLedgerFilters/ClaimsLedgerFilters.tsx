import type { ClaimsFilters } from '../../../claims/claimsClient';
import {
  CAMPAIGN_CLASS_LABELS,
  CLAIM_SORT_LABELS,
  CLAIM_SOURCE_LABELS,
  COMMERCE_RAIL_LABELS,
  COMMERCE_TRUTH_SOURCE_LABELS,
  DISCREPANCY_CLASS_LABELS,
  POLICY_AUTHORITY_LABELS,
  POLICY_AUTHORITY_STATES,
  VERIFICATION_STATUS_LABELS,
} from '../../../claims/claimsFilterConfig';
import {
  CLAIMS_DATE_RANGE_LABELS,
  CLAIMS_DATE_RANGE_PRESETS,
  presetToDateRange,
  resolveDateRangePreset,
  type ClaimsDateRangePreset,
} from '../../../claims/claimsDateRange';
import { ALLOWED_CLAIM_SORT_KEYS, ALLOWED_DISCREPANCY_CLASSES } from '../../../ledger/claimsQueryState';
import { IconCalendar, IconSearch } from '../../icons/StatusIcons';
import shared from '../../../styles/shared.module.css';
import styles from './ClaimsLedgerFilters.module.css';

export interface ClaimsLedgerFiltersProps {
  filters: ClaimsFilters;
  onChange: (filters: ClaimsFilters) => void;
}

export function ClaimsLedgerFilters({ filters, onChange }: ClaimsLedgerFiltersProps) {
  const datePreset = resolveDateRangePreset(filters.dateFrom, filters.dateTo);

  const update = (patch: Partial<ClaimsFilters>) => {
    onChange({ ...filters, ...patch, offset: 0 });
  };

  const handleDatePresetChange = (preset: ClaimsDateRangePreset) => {
    const range = presetToDateRange(preset);
    update({ dateFrom: range.dateFrom, dateTo: range.dateTo });
  };

  return (
    <section className={styles.panel} data-claims-filters aria-label="Claims ledger filters">
      <div className={styles.dimensionRow} data-claims-dimension-filters>
        <label className={styles.field}>
          <span className={styles.fieldLabel}>Claim source (platform)</span>
          <select
            className={[styles.control, shared.focusVisible].join(' ')}
            value={filters.claimSource ?? ''}
            onChange={(e) => update({ claimSource: e.target.value || undefined })}
            aria-label="Claim source (platform)"
            data-claims-filter-claim-source
          >
            <option value="">All platforms</option>
            {Object.entries(CLAIM_SOURCE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>Campaign class</span>
          <select
            className={[styles.control, shared.focusVisible].join(' ')}
            value={filters.campaignClass ?? ''}
            onChange={(e) => update({ campaignClass: e.target.value || undefined })}
            aria-label="Campaign class"
            data-claims-filter-campaign-class
          >
            <option value="">All campaign classes</option>
            {Object.entries(CAMPAIGN_CLASS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>Commerce rail</span>
          <select
            className={[styles.control, shared.focusVisible].join(' ')}
            value={filters.commerceRail ?? ''}
            onChange={(e) => update({ commerceRail: e.target.value || undefined })}
            aria-label="Commerce rail"
            data-claims-filter-commerce-rail
          >
            <option value="">All commerce rails</option>
            {Object.entries(COMMERCE_RAIL_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className={styles.dropdownRow}>
        <label className={styles.field}>
          <span className={styles.fieldLabel}>
            <IconCalendar className={styles.fieldIcon} aria-hidden />
            Date range
          </span>
          <select
            className={[styles.control, shared.focusVisible].join(' ')}
            value={datePreset}
            onChange={(e) => {
              const next = e.target.value as ClaimsDateRangePreset | 'custom';
              if (next !== 'custom') handleDatePresetChange(next);
            }}
            aria-label="Date range"
          >
            {CLAIMS_DATE_RANGE_PRESETS.map((preset) => (
              <option key={preset} value={preset}>
                {CLAIMS_DATE_RANGE_LABELS[preset]}
              </option>
            ))}
            {datePreset === 'custom' ? (
              <option value="custom" disabled>
                Custom range
              </option>
            ) : null}
          </select>
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>Commerce truth</span>
          <select
            className={[styles.control, shared.focusVisible].join(' ')}
            value={filters.commerceSource ?? ''}
            onChange={(e) => update({ commerceSource: e.target.value || undefined })}
            aria-label="Commerce truth"
          >
            <option value="">All</option>
            {Object.entries(COMMERCE_TRUTH_SOURCE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>Verification status</span>
          <select
            className={[styles.control, shared.focusVisible].join(' ')}
            value={filters.verificationStatus ?? ''}
            onChange={(e) => update({ verificationStatus: e.target.value || undefined })}
            aria-label="Verification status"
          >
            <option value="">All</option>
            {Object.entries(VERIFICATION_STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>Discrepancy class</span>
          <select
            className={[styles.control, shared.focusVisible].join(' ')}
            value={filters.discrepancyClass ?? ''}
            onChange={(e) => update({ discrepancyClass: e.target.value || undefined })}
            aria-label="Discrepancy class"
          >
            <option value="">All</option>
            {ALLOWED_DISCREPANCY_CLASSES.map((value) => (
              <option key={value} value={value}>
                {DISCREPANCY_CLASS_LABELS[value]}
              </option>
            ))}
          </select>
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>Policy authority</span>
          <select
            className={[styles.control, shared.focusVisible].join(' ')}
            value={filters.policyAuthority ?? ''}
            onChange={(e) => update({ policyAuthority: e.target.value || undefined })}
            aria-label="Policy authority"
          >
            <option value="">All</option>
            {POLICY_AUTHORITY_STATES.map((value) => (
              <option key={value} value={value}>
                {POLICY_AUTHORITY_LABELS[value]}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className={styles.searchRow}>
        <label className={styles.searchField}>
          <span className={styles.visuallyHidden}>Search by claim reference</span>
          <IconSearch className={styles.searchIcon} aria-hidden />
          <input
            type="search"
            className={[styles.searchInput, shared.focusVisible].join(' ')}
            value={filters.search ?? ''}
            placeholder="Search by claim reference"
            aria-label="Search by claim reference"
            onChange={(e) => update({ search: e.target.value || undefined })}
          />
        </label>
      </div>

      <div className={styles.sortRow}>
        <label className={styles.sortField}>
          <span className={styles.fieldLabel}>Sort by</span>
          <select
            className={[styles.control, styles.sortControl, shared.focusVisible].join(' ')}
            value={filters.sortKey ?? 'lastUpdated'}
            onChange={(e) => update({ sortKey: e.target.value })}
            aria-label="Sort by"
          >
            {ALLOWED_CLAIM_SORT_KEYS.map((key) => (
              <option key={key} value={key}>
                {CLAIM_SORT_LABELS[key] ?? key}
              </option>
            ))}
          </select>
        </label>
      </div>
    </section>
  );
}
