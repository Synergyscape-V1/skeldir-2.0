import type { ExceptionsFilters } from '../../../exceptions/exceptionsClient';
import {
  EXCEPTION_CATEGORY_LABELS,
  EXCEPTION_POLICY_FILTER_LABELS,
  EXCEPTION_SEVERITY_LABELS,
  EXCEPTION_SOURCE_OBJECT_OPTIONS,
  EXCEPTION_STATUS_LABELS,
  EXCEPTIONS_PAGE_COPY,
} from '../../../exceptions/copy';
import {
  buildActiveExceptionFilterChips,
  clearExceptionFilterChip,
  EXCEPTION_CATEGORY_ORDER,
  hasActiveExceptionsFilters,
} from '../../../exceptions/exceptionsFilterConfig';
import { EXCEPTION_DEFAULT_DATE_FROM, EXCEPTION_DEFAULT_DATE_TO } from '../../../exceptions/exceptionsFixtures';
import {
  CLAIMS_DATE_RANGE_LABELS,
  CLAIMS_DATE_RANGE_PRESETS,
  presetToDateRange,
  resolveDateRangePreset,
} from '../../../claims/claimsDateRange';
import { POLICY_AUTHORITY_STATES } from '../../../lib/types';
import { IconCalendar, IconRefresh, IconSearch } from '../../icons/StatusIcons';
import shared from '../../../styles/shared.module.css';
import styles from './ExceptionsFilters.module.css';

export interface ExceptionsFiltersProps {
  filters: ExceptionsFilters;
  onChange: (filters: ExceptionsFilters) => void;
  onClearAll?: () => void;
  disabled?: boolean;
}

const DATE_PRESET_OPTIONS: Array<{ value: string; label: string; from?: string; to?: string }> = [
  ...CLAIMS_DATE_RANGE_PRESETS.map((preset) => ({
    value: preset,
    label: CLAIMS_DATE_RANGE_LABELS[preset],
    ...presetToDateRange(preset),
  })),
  {
    value: 'fixture_window',
    label: 'Last 7 days',
    from: EXCEPTION_DEFAULT_DATE_FROM,
    to: EXCEPTION_DEFAULT_DATE_TO,
  },
];

export function ExceptionsFiltersPanel({
  filters,
  onChange,
  onClearAll,
  disabled = false,
}: ExceptionsFiltersProps) {
  const datePreset = resolveDateRangePreset(filters.dateFrom, filters.dateTo);
  const chips = buildActiveExceptionFilterChips(filters);
  const showChipRow = hasActiveExceptionsFilters(filters);

  const update = (patch: Partial<ExceptionsFilters>) => {
    onChange({ ...filters, ...patch, offset: 0 });
  };

  const handleDateChange = (value: string) => {
    const option = DATE_PRESET_OPTIONS.find((entry) => entry.value === value);
    if (!option?.from || !option.to) return;
    update({ dateFrom: option.from, dateTo: option.to });
  };

  const selectedDateValue =
    filters.dateFrom === EXCEPTION_DEFAULT_DATE_FROM && filters.dateTo === EXCEPTION_DEFAULT_DATE_TO
      ? 'fixture_window'
      : datePreset;

  return (
    <section className={styles.panel} data-exceptions-filters aria-label="Exception queue filters">
      <div className={styles.primaryRow}>
        <label className={styles.field}>
          <span className={styles.fieldLabel}>
            <IconCalendar className={styles.fieldIcon} aria-hidden />
            {EXCEPTIONS_PAGE_COPY.filters.dateRange}
          </span>
          <select
            className={[styles.control, shared.focusVisible].join(' ')}
            value={selectedDateValue}
            disabled={disabled}
            aria-label={EXCEPTIONS_PAGE_COPY.filters.dateRange}
            onChange={(e) => handleDateChange(e.target.value)}
          >
            {DATE_PRESET_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>{EXCEPTIONS_PAGE_COPY.filters.category}</span>
          <select
            className={[styles.control, shared.focusVisible].join(' ')}
            value={filters.category ?? 'all'}
            disabled={disabled}
            aria-label={EXCEPTIONS_PAGE_COPY.filters.category}
            onChange={(e) =>
              update({ category: (e.target.value || 'all') as ExceptionsFilters['category'] })
            }
          >
            <option value="all">{EXCEPTIONS_PAGE_COPY.filters.all}</option>
            {EXCEPTION_CATEGORY_ORDER.map((category) => (
              <option key={category} value={category}>
                {EXCEPTION_CATEGORY_LABELS[category]}
              </option>
            ))}
          </select>
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>{EXCEPTIONS_PAGE_COPY.filters.severity}</span>
          <select
            className={[styles.control, shared.focusVisible].join(' ')}
            value={filters.severity ?? 'all'}
            disabled={disabled}
            aria-label={EXCEPTIONS_PAGE_COPY.filters.severity}
            onChange={(e) =>
              update({ severity: (e.target.value || 'all') as ExceptionsFilters['severity'] })
            }
          >
            <option value="all">{EXCEPTIONS_PAGE_COPY.filters.all}</option>
            {(['critical', 'warning', 'info'] as const).map((severity) => (
              <option key={severity} value={severity}>
                {EXCEPTION_SEVERITY_LABELS[severity]}
              </option>
            ))}
          </select>
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>{EXCEPTIONS_PAGE_COPY.filters.status}</span>
          <select
            className={[styles.control, shared.focusVisible].join(' ')}
            value={filters.status ?? 'all'}
            disabled={disabled}
            aria-label={EXCEPTIONS_PAGE_COPY.filters.status}
            onChange={(e) => update({ status: (e.target.value || 'all') as ExceptionsFilters['status'] })}
          >
            <option value="all">{EXCEPTIONS_PAGE_COPY.filters.all}</option>
            {(['open', 'acknowledged', 'suppressed', 'resolved'] as const).map((status) => (
              <option key={status} value={status}>
                {EXCEPTION_STATUS_LABELS[status]}
              </option>
            ))}
          </select>
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>{EXCEPTIONS_PAGE_COPY.filters.policyAuthority}</span>
          <select
            className={[styles.control, shared.focusVisible].join(' ')}
            value={filters.policyAuthority ?? 'all'}
            disabled={disabled}
            aria-label={EXCEPTIONS_PAGE_COPY.filters.policyAuthority}
            onChange={(e) =>
              update({
                policyAuthority: (e.target.value || 'all') as ExceptionsFilters['policyAuthority'],
              })
            }
          >
            <option value="all">{EXCEPTIONS_PAGE_COPY.filters.all}</option>
            {POLICY_AUTHORITY_STATES.map((state) => (
              <option key={state} value={state}>
                {EXCEPTION_POLICY_FILTER_LABELS[state]}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className={styles.secondaryRow}>
        <label className={styles.field}>
          <span className={styles.fieldLabel}>{EXCEPTIONS_PAGE_COPY.filters.sourceObject}</span>
          <select
            className={[styles.control, shared.focusVisible].join(' ')}
            value={filters.sourceObject ?? 'all'}
            disabled={disabled}
            aria-label={EXCEPTIONS_PAGE_COPY.filters.sourceObject}
            onChange={(e) => update({ sourceObject: e.target.value || 'all' })}
          >
            <option value="all">{EXCEPTIONS_PAGE_COPY.filters.all}</option>
            {EXCEPTION_SOURCE_OBJECT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className={styles.searchField}>
          <span className={styles.visuallyHidden}>{EXCEPTIONS_PAGE_COPY.filters.searchPlaceholder}</span>
          <IconSearch className={styles.searchIcon} aria-hidden />
          <input
            type="search"
            className={[styles.searchInput, shared.focusVisible].join(' ')}
            value={filters.search ?? ''}
            disabled={disabled}
            placeholder={EXCEPTIONS_PAGE_COPY.filters.searchPlaceholder}
            aria-label={EXCEPTIONS_PAGE_COPY.filters.searchPlaceholder}
            onChange={(e) => update({ search: e.target.value || undefined })}
          />
        </label>

        {onClearAll ? (
          <button
            type="button"
            className={[styles.clearFilters, shared.focusVisible].join(' ')}
            disabled={disabled || !showChipRow}
            onClick={onClearAll}
            data-exceptions-clear-filters
          >
            <IconRefresh className={styles.clearIcon} aria-hidden />
            {EXCEPTIONS_PAGE_COPY.filters.clearFilters}
          </button>
        ) : null}
      </div>

      {showChipRow ? (
        <div className={styles.chipRow}>
          <div className={styles.chips} role="list" aria-label="Active filters">
            {chips.map((chip) => (
              <span key={chip.key} className={styles.chip} role="listitem">
                <span>{chip.label}</span>
                <button
                  type="button"
                  className={[styles.chipRemove, shared.focusVisible].join(' ')}
                  aria-label={`Remove ${chip.label} filter`}
                  onClick={() => onChange(clearExceptionFilterChip(filters, chip.key))}
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}
