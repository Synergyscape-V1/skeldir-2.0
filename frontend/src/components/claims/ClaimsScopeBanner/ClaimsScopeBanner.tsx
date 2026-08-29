import { IconProhibited } from '../../icons/StatusIcons';
import { resolveChannelLogoSrc, isChannelLogoPlaceholder } from '../../commandCenter/ChannelLogo/channelLogoMap';
import shared from '../../../styles/shared.module.css';
import styles from './ClaimsScopeBanner.module.css';

export interface ClaimsScopeFilterEntry {
  key: string;
  label: string;
  /** Raw vendor/platform value; when resolvable, renders a brand mark instead of a plain text pill. */
  logoKey?: string;
}

export interface ClaimsScopeBannerProps {
  activeFilters: ClaimsScopeFilterEntry[];
  onRemoveFilter: (key: string) => void;
  onClearAll: () => void;
  permissionErrors?: string[];
  totalCount?: number;
}

/**
 * GlobalScopeIndicator — Audit 2 remediation.
 *
 * Ambient statement of active data scope between page header and table.
 * Active-filter chips share the same filterChip DNA as ExceptionsCategoryTabs /
 * BenchmarksFilters (rectangular supervisory chips, not pills or warning strips).
 */
export function ClaimsScopeBanner({
  activeFilters,
  onRemoveFilter,
  onClearAll,
  permissionErrors = [],
  totalCount,
}: ClaimsScopeBannerProps) {
  const hasFilters = activeFilters.length > 0;

  if (!hasFilters) {
    return (
      <section
        className={[styles.banner, styles.unfiltered].join(' ')}
        data-claims-scope-banner
        data-scope-state="unfiltered"
        role="status"
        aria-label="Data scope"
      >
        <span className={styles.summary}>Viewing all revenue claims.</span>
      </section>
    );
  }

  const permissionErrorSet = new Set(permissionErrors);

  return (
    <section
      className={[styles.banner, styles.filtered].join(' ')}
      data-claims-scope-banner
      data-scope-state="filtered"
      role="status"
      aria-live="polite"
      aria-label="Active data scope"
    >
      <div className={styles.row}>
        <span className={styles.summary}>
          {totalCount !== undefined
            ? `Viewing ${totalCount.toLocaleString()} claim${totalCount === 1 ? '' : 's'} matching filters:`
            : 'Viewing filtered claims:'}
        </span>

        <ul className={styles.chips} role="list" aria-label="Active filters">
          {activeFilters.map((entry) => {
            const denied = permissionErrorSet.has(entry.key);
            const logoSrc = entry.logoKey ? resolveChannelLogoSrc(entry.logoKey) : undefined;
            const showLogo = Boolean(logoSrc) && !isChannelLogoPlaceholder(entry.logoKey ?? '');

            return (
              <li key={entry.key} className={styles.chipItem} role="listitem">
                <span
                  className={[styles.chip, denied ? styles.chipDenied : ''].filter(Boolean).join(' ')}
                  data-filter-key={entry.key}
                  data-permission-error={denied ? 'true' : undefined}
                  aria-label={denied ? `${entry.label} (insufficient permissions)` : entry.label}
                >
                  {showLogo ? (
                    <img
                      src={logoSrc}
                      alt=""
                      className={styles.chipLogo}
                      data-channel-logo={entry.logoKey}
                      aria-hidden="true"
                    />
                  ) : null}
                  {showLogo ? null : <span>{entry.label}</span>}
                  {denied ? (
                    <span className={styles.deniedBadge} aria-hidden="true">
                      <IconProhibited className={styles.deniedIcon} />
                    </span>
                  ) : null}
                  <button
                    type="button"
                    className={[styles.chipRemove, shared.focusVisible].join(' ')}
                    aria-label={`Remove ${entry.label} filter`}
                    onClick={() => onRemoveFilter(entry.key)}
                  >
                    ×
                  </button>
                </span>
                {denied ? (
                  <span className={styles.deniedTooltip} role="tooltip">
                    Insufficient permissions for this filter.
                  </span>
                ) : null}
              </li>
            );
          })}
        </ul>

        <button
          type="button"
          className={[styles.clearAll, shared.focusVisible].join(' ')}
          onClick={onClearAll}
          aria-label="Clear all active filters"
        >
          Clear all filters
        </button>
      </div>
    </section>
  );
}
