import type { BenchmarksFilters } from '../../../benchmarks/benchmarksClient';
import { BENCHMARKS_COPY } from '../../../benchmarks/copy';
import {
  BENCHMARK_ACTIONABILITY_OPTIONS,
  BENCHMARK_CHANNEL_OPTIONS,
  BENCHMARK_COMMERCE_OPTIONS,
  BENCHMARK_COVERAGE_OPTIONS,
  BENCHMARK_DEFAULT_DATE_FROM,
  BENCHMARK_DEFAULT_DATE_TO,
  BENCHMARK_EVIDENCE_OPTIONS,
  BENCHMARK_PLATFORM_OPTIONS,
} from '../../../benchmarks/benchmarksFixtures';
import {
  buildActiveBenchmarkFilterChips,
  BENCHMARK_FILTER_LABELS,
  clearBenchmarkFilterChip,
  hasActiveBenchmarkFilters,
} from '../../../benchmarks/benchmarksFilterConfig';
import { IconCalendar } from '../../icons/StatusIcons';
import shared from '../../../styles/shared.module.css';
import styles from './BenchmarksFilters.module.css';

export interface BenchmarksFiltersProps {
  filters: BenchmarksFilters;
  onChange: (filters: BenchmarksFilters) => void;
  onClearAll?: () => void;
  disabled?: boolean;
}

function dateRangeLabel(filters: BenchmarksFilters): string {
  if (filters.dateFrom === BENCHMARK_DEFAULT_DATE_FROM && filters.dateTo === BENCHMARK_DEFAULT_DATE_TO) {
    return 'Apr 1, 2026 – Jun 30, 2026';
  }
  if (filters.dateFrom && filters.dateTo) return `${filters.dateFrom} – ${filters.dateTo}`;
  return 'All dates';
}

export function BenchmarksFilters({
  filters,
  onChange,
  onClearAll,
  disabled = false,
}: BenchmarksFiltersProps) {
  const chips = buildActiveBenchmarkFilterChips(filters);
  const showChipRow = hasActiveBenchmarkFilters(filters);

  const update = (patch: Partial<BenchmarksFilters>) => {
    onChange({ ...filters, ...patch, offset: 0 });
  };

  const toggleListValue = (key: 'platformIds' | 'commerceSourceIds', value: string) => {
    const current = filters[key] ?? [];
    const next = current.includes(value) ? current.filter((item) => item !== value) : [...current, value];
    update({ [key]: next.length ? next : undefined });
  };

  const handleRemoveChip = (chipKey: Parameters<typeof clearBenchmarkFilterChip>[1], chipLabel?: string) => {
    onChange(clearBenchmarkFilterChip(filters, chipKey, chipLabel));
  };

  return (
    <section className={styles.panel} data-benchmarks-filters aria-label="Filter benchmarks">
      <h2 className={styles.heading}>{BENCHMARKS_COPY.filters.heading}</h2>

      <div className={styles.primaryRow}>
        <label className={[styles.field, styles.dateField].join(' ')}>
          <span className={styles.fieldLabel}>
            <IconCalendar className={styles.fieldIcon} aria-hidden />
            {BENCHMARKS_COPY.filters.dateRange}
          </span>
          <select
            className={[styles.control, shared.focusVisible].join(' ')}
            value={`${filters.dateFrom ?? ''}|${filters.dateTo ?? ''}`}
            disabled={disabled}
            aria-label={BENCHMARKS_COPY.filters.dateRange}
            onChange={(e) => {
              const [from, to] = e.target.value.split('|');
              update({ dateFrom: from || undefined, dateTo: to || undefined });
            }}
          >
            <option value={`${BENCHMARK_DEFAULT_DATE_FROM}|${BENCHMARK_DEFAULT_DATE_TO}`}>
              Apr 1, 2026 – Jun 30, 2026
            </option>
            <option value="|">All dates</option>
          </select>
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>{BENCHMARKS_COPY.filters.channel}</span>
          <select
            className={[styles.control, shared.focusVisible].join(' ')}
            value={filters.channelId ?? ''}
            disabled={disabled}
            aria-label={BENCHMARKS_COPY.filters.channel}
            onChange={(e) => update({ channelId: e.target.value || undefined })}
          >
            <option value="">{BENCHMARKS_COPY.filters.allChannels}</option>
            {BENCHMARK_CHANNEL_OPTIONS.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>{BENCHMARKS_COPY.filters.platform}</span>
          <select
            className={[styles.control, shared.focusVisible].join(' ')}
            value=""
            disabled={disabled}
            aria-label={BENCHMARKS_COPY.filters.platform}
            onChange={(e) => {
              if (e.target.value) toggleListValue('platformIds', e.target.value);
            }}
          >
            <option value="">{BENCHMARK_FILTER_LABELS.platformDisplay(filters.platformIds)}</option>
            {BENCHMARK_PLATFORM_OPTIONS.map((option) => (
              <option key={option.id} value={option.id}>
                {filters.platformIds?.includes(option.id) ? `✓ ${option.label}` : option.label}
              </option>
            ))}
          </select>
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>{BENCHMARKS_COPY.filters.commerceSource}</span>
          <select
            className={[styles.control, shared.focusVisible].join(' ')}
            value=""
            disabled={disabled}
            aria-label={BENCHMARKS_COPY.filters.commerceSource}
            onChange={(e) => {
              if (e.target.value) toggleListValue('commerceSourceIds', e.target.value);
            }}
          >
            <option value="">{BENCHMARK_FILTER_LABELS.commerceDisplay(filters.commerceSourceIds)}</option>
            {BENCHMARK_COMMERCE_OPTIONS.map((option) => (
              <option key={option.id} value={option.id}>
                {filters.commerceSourceIds?.includes(option.id) ? `✓ ${option.label}` : option.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className={styles.secondaryRow}>
        <label className={styles.field}>
          <span className={styles.fieldLabel}>{BENCHMARKS_COPY.filters.evidenceClass}</span>
          <select
            className={[styles.control, shared.focusVisible].join(' ')}
            value={filters.evidenceClass ?? ''}
            disabled={disabled}
            aria-label={BENCHMARKS_COPY.filters.evidenceClass}
            onChange={(e) =>
              update({ evidenceClass: (e.target.value || undefined) as BenchmarksFilters['evidenceClass'] })
            }
          >
            <option value="">{BENCHMARKS_COPY.filters.allEvidenceClasses}</option>
            {BENCHMARK_EVIDENCE_OPTIONS.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>{BENCHMARKS_COPY.filters.coverageClass}</span>
          <select
            className={[styles.control, shared.focusVisible].join(' ')}
            value={filters.coverageClass ?? ''}
            disabled={disabled}
            aria-label={BENCHMARKS_COPY.filters.coverageClass}
            onChange={(e) =>
              update({ coverageClass: (e.target.value || undefined) as BenchmarksFilters['coverageClass'] })
            }
          >
            <option value="">{BENCHMARKS_COPY.filters.allCoverageClasses}</option>
            {BENCHMARK_COVERAGE_OPTIONS.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>{BENCHMARKS_COPY.filters.actionability}</span>
          <select
            className={[styles.control, shared.focusVisible].join(' ')}
            value={filters.actionability ?? ''}
            disabled={disabled}
            aria-label={BENCHMARKS_COPY.filters.actionability}
            onChange={(e) =>
              update({ actionability: (e.target.value || undefined) as BenchmarksFilters['actionability'] })
            }
          >
            <option value="">{BENCHMARKS_COPY.filters.allActionability}</option>
            {BENCHMARK_ACTIONABILITY_OPTIONS.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        {showChipRow && onClearAll ? (
          <button
            type="button"
            className={[styles.clearFilters, shared.focusVisible].join(' ')}
            disabled={disabled}
            onClick={onClearAll}
            data-benchmarks-clear-filters
          >
            {BENCHMARKS_COPY.filters.clearFilters}
          </button>
        ) : null}
      </div>

      {showChipRow ? (
        <div className={styles.chipRow}>
          <div className={styles.chips} role="list" aria-label="Active filters">
            {chips.map((chip) => (
              <span key={`${chip.key}-${chip.label}`} className={styles.chip} role="listitem">
                <span>{chip.label}</span>
                <button
                  type="button"
                  className={[styles.chipRemove, shared.focusVisible].join(' ')}
                  aria-label={`Remove ${chip.label} filter`}
                  onClick={() => handleRemoveChip(chip.key, chip.label)}
                >
                  ×
                </button>
              </span>
            ))}
          </div>
          <span className={styles.visuallyHidden}>Date range currently {dateRangeLabel(filters)}</span>
        </div>
      ) : null}
    </section>
  );
}
