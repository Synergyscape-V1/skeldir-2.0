import type { ChannelOverviewRowDTO } from '../../../ledger/types';
import { formatMoneyMinorDisplay } from '../../../lib/money';
import { CHANNELS_OVERVIEW_COPY } from '../../../channels/copy';
import { channelRowIdentityLabel, channelsClaimSourceLabel } from '../../../channels/channelsDisplay';
import {
  COMMAND_CENTER_POLICY_CHIP_PROPS,
  SUPERVISORY_TABLE_STATUS_TEXT,
} from '../../../commandCenter/commandCenterChipProps';
import {
  BayesianStatusBadge,
  BenchmarkStatusBadge,
  DiscrepancyBadge,
  formatDiscrepancyPercent,
} from '../../commandCenter/StatusBadges/StatusBadges';
import { PolicyAuthorityPill } from '../../trust/PolicyAuthorityPill/PolicyAuthorityPill';
import { RevenueReliabilityBadge } from '../../trust/RevenueReliabilityBadge/RevenueReliabilityBadge';
import { resolveRevenueReliabilityFromAgreementPercent } from '../../../trust/revenueReliability';
import { ChannelLogo } from '../../commandCenter/ChannelLogo/ChannelLogo';
import shared from '../../../styles/shared.module.css';
import styles from './ChannelsOverviewTableCells.module.css';

export function ChannelsAttributionChannelCell({
  row,
  expanded = false,
  onToggle,
}: {
  row: ChannelOverviewRowDTO;
  expanded?: boolean;
  onToggle?: (row: ChannelOverviewRowDTO) => void;
}) {
  const identity = channelRowIdentityLabel(row);
  return (
    <div className={styles.attributionChannelCell}>
      <button
        type="button"
        className={[styles.channelLink, styles.channelExpandButton, shared.focusVisible].join(' ')}
        data-channel-link={row.channelId}
        data-attribution-channel={row.attributionChannel}
        data-channel-expand-trigger={row.channelId}
        aria-expanded={expanded}
        title={identity}
        onClick={(event) => {
          event.stopPropagation();
          onToggle?.(row);
        }}
      >
        {row.channelName}
      </button>
    </div>
  );
}

export function ChannelsClaimSourceCell({ row }: { row: ChannelOverviewRowDTO }) {
  const label = channelsClaimSourceLabel(row.claimSource);
  return (
    <div className={styles.claimSourceCell} data-claim-source-cell={row.claimSource}>
      <ChannelLogo claimSource={row.claimSource} />
      <span className={styles.claimSourceLabel} title={label}>
        {label}
      </span>
    </div>
  );
}

export function ChannelsVerifiedRevenueCell({ row }: { row: ChannelOverviewRowDTO }) {
  return (
    <span
      className={styles.moneyStrong}
      data-verified-revenue-minor={row.verifiedRevenueMinor.toString()}
      title={`${row.verifiedRevenueMinor.toString()} minor units`}
    >
      {formatMoneyMinorDisplay(row.verifiedRevenueMinor, row.currencyCode)}
    </span>
  );
}

export function ChannelsClaimedRevenueCell({ row }: { row: ChannelOverviewRowDTO }) {
  return (
    <span
      className={styles.moneyStrong}
      data-claimed-revenue-minor={row.claimedRevenueMinor.toString()}
      title={`${row.claimedRevenueMinor.toString()} minor units`}
    >
      {formatMoneyMinorDisplay(row.claimedRevenueMinor, row.currencyCode)}
    </span>
  );
}

export function ChannelsDiscrepancyCell({ row }: { row: ChannelOverviewRowDTO }) {
  return (
    <div className={styles.discrepancyCell}>
      <span>{formatDiscrepancyPercent(row.discrepancyRateBps)}</span>
      <DiscrepancyBadge status={row.discrepancyStatus} {...SUPERVISORY_TABLE_STATUS_TEXT} />
    </div>
  );
}

export function ChannelsRevenueReliabilityCell({ row }: { row: ChannelOverviewRowDTO }) {
  const resolution = resolveRevenueReliabilityFromAgreementPercent(row.attributionModelAgreement);
  return (
    <RevenueReliabilityBadge
      state={resolution.state}
      invalid={resolution.invalid}
      data-channel-revenue-reliability={resolution.state}
    />
  );
}

export function ChannelsBayesianCell({ row }: { row: ChannelOverviewRowDTO }) {
  const statusKey =
    row.bayesianStatusKey === 'degraded' ? 'unavailable' : row.bayesianStatusKey === 'healthy' ? 'healthy' : row.bayesianStatusKey;
  return (
    <div className={styles.metaCell}>
      <BayesianStatusBadge status={statusKey as 'healthy' | 'unavailable' | 'delayed' | 'low_confidence'} {...SUPERVISORY_TABLE_STATUS_TEXT} />
      {row.bayesianStabilityLabel ? (
        <span className={styles.truncatedMetaText} title={row.bayesianStabilityLabel}>
          {row.bayesianStabilityLabel}
        </span>
      ) : null}
    </div>
  );
}

export function ChannelsBenchmarkCell({ row }: { row: ChannelOverviewRowDTO }) {
  const statusKey =
    row.benchmarkStatusKey === 'attention_needed' ? 'unavailable' : row.benchmarkStatusKey;
  return (
    <div className={styles.metaCell}>
      <BenchmarkStatusBadge status={statusKey as 'stable' | 'transitioning' | 'unavailable' | 'suppressed'} {...SUPERVISORY_TABLE_STATUS_TEXT} />
      {row.benchmarkPositionLabel ? (
        <span className={styles.truncatedMetaText} title={row.benchmarkPositionLabel}>
          {row.benchmarkPositionLabel}
        </span>
      ) : null}
    </div>
  );
}

export function ChannelsPolicyCell({ row }: { row: ChannelOverviewRowDTO }) {
  return (
    <PolicyAuthorityPill
      state={row.policyAuthority}
      {...COMMAND_CENTER_POLICY_CHIP_PROPS}
      appearance="text"
    />
  );
}

export function ChannelsOpenCell({
  row,
  disabled,
  expanded = false,
  onToggle,
}: {
  row: ChannelOverviewRowDTO;
  disabled?: boolean;
  expanded?: boolean;
  onToggle?: (row: ChannelOverviewRowDTO) => void;
}) {
  const label = expanded ? CHANNELS_OVERVIEW_COPY.table.hideDetails : CHANNELS_OVERVIEW_COPY.table.viewDetails;
  return (
    <button
      type="button"
      className={[styles.openButton, shared.focusVisible].join(' ')}
      disabled={disabled}
      data-channel-open={row.channelId}
      aria-expanded={expanded}
      aria-label={`${label} for ${channelRowIdentityLabel(row)}`}
      onClick={(event) => {
        event.stopPropagation();
        onToggle?.(row);
      }}
    >
      {expanded ? 'Hide' : CHANNELS_OVERVIEW_COPY.table.open}
    </button>
  );
}
