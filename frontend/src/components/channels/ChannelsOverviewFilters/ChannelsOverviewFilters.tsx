import type { ChannelsFilters } from '../../../channels/channelsClient';
import { CHANNELS_OVERVIEW_COPY } from '../../../channels/copy';
import {
  buildActiveChannelsFilterChips,
  CHANNEL_FILTER_LABELS,
  clearChannelsFilterChip,
  hasActiveChannelsFilters,
  POLICY_AUTHORITY_LABELS,
  POLICY_AUTHORITY_STATES,
} from '../../../channels/channelsFilterConfig';
import {
  CLAIMS_DATE_RANGE_LABELS,
  CLAIMS_DATE_RANGE_PRESETS,
  presetToDateRange,
  resolveDateRangePreset,
  type ClaimsDateRangePreset,
} from '../../../claims/claimsDateRange';
import { IconCalendar, IconSearch } from '../../icons/StatusIcons';
import shared from '../../../styles/shared.module.css';
import styles from './ChannelsOverviewFilters.module.css';

export interface ChannelsOverviewFiltersProps {
  filters: ChannelsFilters;
  onChange: (filters: ChannelsFilters) => void;
  onClearAll?: () => void;
  disabled?: boolean;
}

export function ChannelsOverviewFilters({
  filters,
  onChange,
  onClearAll,
  disabled = false,
}: ChannelsOverviewFiltersProps) {
  const datePreset = resolveDateRangePreset(filters.dateFrom, filters.dateTo);
  const chips = buildActiveChannelsFilterChips(filters);
  const showChipRow = hasActiveChannelsFilters(filters);

  const update = (patch: Partial<ChannelsFilters>) => {
    onChange({ ...filters, ...patch, offset: 0 });
  };

  const handleDatePresetChange = (preset: ClaimsDateRangePreset) => {
    const range = presetToDateRange(preset);
    update({ dateFrom: range.dateFrom, dateTo: range.dateTo });
  };

  const handleRemoveChip = (chipKey: Parameters<typeof clearChannelsFilterChip>[1]) => {
    onChange(clearChannelsFilterChip(filters, chipKey));
  };

  return (
    <section className={styles.panel} data-channels-filters aria-label="Channel trust filters">
      <div className={styles.primaryRow}>
        <label className={styles.field}>
          <span className={styles.fieldLabel}>
            <IconCalendar className={styles.fieldIcon} aria-hidden />
            {CHANNELS_OVERVIEW_COPY.filters.dateRange}
          </span>
          <select
            className={[styles.control, shared.focusVisible].join(' ')}
            value={datePreset}
            disabled={disabled}
            onChange={(e) => {
              const next = e.target.value as ClaimsDateRangePreset | 'custom';
              if (next !== 'custom') handleDatePresetChange(next);
            }}
            aria-label={CHANNELS_OVERVIEW_COPY.filters.dateRange}
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
          <span className={styles.fieldLabel}>{CHANNELS_OVERVIEW_COPY.filters.attributionChannel}</span>
          <select
            className={[styles.control, shared.focusVisible].join(' ')}
            value={filters.attributionChannel ?? ''}
            disabled={disabled}
            onChange={(e) => update({ attributionChannel: e.target.value || undefined, channelId: undefined })}
            aria-label={CHANNELS_OVERVIEW_COPY.filters.attributionChannel}
          >
            <option value="">All attribution channels</option>
            {Object.entries(CHANNEL_FILTER_LABELS.attributionChannel).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>{CHANNELS_OVERVIEW_COPY.filters.claimSource}</span>
          <select
            className={[styles.control, shared.focusVisible].join(' ')}
            value={filters.claimSource ?? ''}
            disabled={disabled}
            onChange={(e) => update({ claimSource: e.target.value || undefined })}
            aria-label={CHANNELS_OVERVIEW_COPY.filters.claimSource}
          >
            <option value="">All claim sources</option>
            {Object.entries(CHANNEL_FILTER_LABELS.claimSource).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>{CHANNELS_OVERVIEW_COPY.filters.commerceSource}</span>
          <select
            className={[styles.control, shared.focusVisible].join(' ')}
            value={filters.commerceSource ?? ''}
            disabled={disabled}
            onChange={(e) => update({ commerceSource: e.target.value || undefined })}
            aria-label={CHANNELS_OVERVIEW_COPY.filters.commerceSource}
          >
            <option value="">All commerce sources</option>
            {Object.entries(CHANNEL_FILTER_LABELS.commerceSource).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className={styles.secondaryRow}>
        <label className={styles.field}>
          <span className={styles.fieldLabel}>{CHANNELS_OVERVIEW_COPY.filters.revenueReliability}</span>
          <select
            className={[styles.control, shared.focusVisible].join(' ')}
            value={filters.attributionAgreement ?? ''}
            disabled={disabled}
            onChange={(e) =>
              update({
                attributionAgreement: (e.target.value || undefined) as ChannelsFilters['attributionAgreement'],
              })
            }
            aria-label={CHANNELS_OVERVIEW_COPY.filters.revenueReliability}
          >
            <option value="">All</option>
            {Object.entries(CHANNEL_FILTER_LABELS.attributionAgreement)
              .filter(([key]) => key !== 'all')
              .map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
          </select>
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>{CHANNELS_OVERVIEW_COPY.filters.bayesianStatus}</span>
          <select
            className={[styles.control, shared.focusVisible].join(' ')}
            value={filters.bayesianStatus ?? ''}
            disabled={disabled}
            onChange={(e) =>
              update({ bayesianStatus: (e.target.value || undefined) as ChannelsFilters['bayesianStatus'] })
            }
            aria-label={CHANNELS_OVERVIEW_COPY.filters.bayesianStatus}
          >
            <option value="">All</option>
            {Object.entries(CHANNEL_FILTER_LABELS.bayesianStatus).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>{CHANNELS_OVERVIEW_COPY.filters.actionAuthority}</span>
          <select
            className={[styles.control, shared.focusVisible].join(' ')}
            value={filters.actionAuthority ?? ''}
            disabled={disabled}
            onChange={(e) => update({ actionAuthority: e.target.value || undefined })}
            aria-label={CHANNELS_OVERVIEW_COPY.filters.actionAuthority}
          >
            <option value="">All</option>
            <option value="actionable_only">Actionable only</option>
            {POLICY_AUTHORITY_STATES.map((value) => (
              <option key={value} value={value}>
                {POLICY_AUTHORITY_LABELS[value]}
              </option>
            ))}
          </select>
        </label>

        <label className={styles.searchField}>
          <span className={styles.visuallyHidden}>{CHANNELS_OVERVIEW_COPY.filters.searchPlaceholder}</span>
          <IconSearch className={styles.searchIcon} aria-hidden />
          <input
            type="search"
            className={[styles.searchInput, shared.focusVisible].join(' ')}
            value={filters.search ?? ''}
            disabled={disabled}
            placeholder={CHANNELS_OVERVIEW_COPY.filters.searchPlaceholder}
            aria-label={CHANNELS_OVERVIEW_COPY.filters.searchPlaceholder}
            onChange={(e) => update({ search: e.target.value || undefined })}
          />
        </label>

        {showChipRow && onClearAll ? (
          <button
            type="button"
            className={[styles.clearFilters, shared.focusVisible].join(' ')}
            disabled={disabled}
            onClick={onClearAll}
            data-channels-clear-filters
          >
            {CHANNELS_OVERVIEW_COPY.filters.clearFilters}
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
                  onClick={() => handleRemoveChip(chip.key)}
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
