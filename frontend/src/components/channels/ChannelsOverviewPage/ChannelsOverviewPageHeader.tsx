import { CHANNELS_OVERVIEW_COPY } from '../../../channels/copy';
import type { ChannelsMetricBasis } from '../../../channels/channelsClient';
import { Typography } from '../../layout/Typography/Typography';
import shared from '../../../styles/shared.module.css';
import styles from './ChannelsOverviewPage.module.css';

export interface ChannelsOverviewPageHeaderProps {
  metricBasis: ChannelsMetricBasis;
  onMetricBasisChange: (basis: ChannelsMetricBasis) => void;
  platformClaimsAvailable?: boolean;
  disabled?: boolean;
}

export function ChannelsOverviewPageHeader({
  metricBasis,
  onMetricBasisChange,
  platformClaimsAvailable = true,
  disabled = false,
}: ChannelsOverviewPageHeaderProps) {
  const showPlatformWarning = metricBasis === 'platform_claim';

  return (
    <>
      <div className={styles.headerRow} data-channels-header-row>
        <header data-channels-header className={styles.pageHeaderStack}>
          <Typography variant="h1" className={styles.pageTitle}>
            {CHANNELS_OVERVIEW_COPY.title}
          </Typography>
          <p className={styles.pageSubtitle}>{CHANNELS_OVERVIEW_COPY.subtitle}</p>
          <p className={styles.pageMetadata}>{CHANNELS_OVERVIEW_COPY.metadataLine}</p>
        </header>
        <div className={styles.headerActionColumn}>
          <div
            className={styles.metricBasisGroup}
            role="radiogroup"
            aria-label={CHANNELS_OVERVIEW_COPY.metricBasis.groupLabel}
            data-channels-metric-basis
          >
            <button
              type="button"
              role="radio"
              aria-checked={metricBasis === 'verified'}
              className={[
                styles.metricBasisButton,
                metricBasis === 'verified' ? styles.metricBasisButtonActive : '',
                shared.focusVisible,
              ]
                .filter(Boolean)
                .join(' ')}
              disabled={disabled}
              onClick={() => onMetricBasisChange('verified')}
              data-metric-basis="verified"
            >
              {CHANNELS_OVERVIEW_COPY.metricBasis.verified}
            </button>
            <button
              type="button"
              role="radio"
              aria-checked={metricBasis === 'platform_claim'}
              className={[
                styles.metricBasisButton,
                metricBasis === 'platform_claim' ? styles.metricBasisButtonActive : '',
                metricBasis === 'platform_claim' ? styles.metricBasisButtonWarning : '',
                shared.focusVisible,
              ]
                .filter(Boolean)
                .join(' ')}
              disabled={disabled || !platformClaimsAvailable}
              title={!platformClaimsAvailable ? CHANNELS_OVERVIEW_COPY.metricBasis.platformDisabledTooltip : undefined}
              onClick={() => onMetricBasisChange('platform_claim')}
              data-metric-basis="platform_claim"
            >
              {CHANNELS_OVERVIEW_COPY.metricBasis.platformClaim}
            </button>
          </div>
        </div>
      </div>
      {showPlatformWarning ? (
        <p
          className={styles.platformWarning}
          role="status"
          data-channels-platform-warning
          aria-live="polite"
        >
          {CHANNELS_OVERVIEW_COPY.metricBasis.platformWarning}
        </p>
      ) : null}
    </>
  );
}
