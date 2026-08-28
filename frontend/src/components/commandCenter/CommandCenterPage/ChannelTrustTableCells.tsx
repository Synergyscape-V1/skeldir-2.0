import { Link, useNavigate } from 'react-router-dom';
import type { KeyboardEvent, ReactNode } from 'react';

import { COMMAND_CENTER_COPY } from '../../../commandCenter/copy';
import {
  benchmarkCellTitle,
  formatChannelDiscrepancyRate,
  discrepancyRateTier,
  resolveAxisLabel,
  showPlatformLogo,
  verifiedRevenueMinorTitle,
} from '../../../commandCenter/channelTrustDisplay';
import type { ChannelTrustGroupBy, ChannelTrustRow } from '../../../commandCenter/types';
import { resolveRevenueReliabilityFromTier } from '../../../trust/revenueReliability';
import { RevenueReliabilityBadge } from '../../trust/RevenueReliabilityBadge/RevenueReliabilityBadge';
import { COMMAND_CENTER_POLICY_CHIP_PROPS } from '../../../commandCenter/commandCenterChipProps';
import { formatMoneyMinorDisplay } from '../../../lib/money';
import { EvidenceClassBadge } from '../../benchmarks/BenchmarkBadges/BenchmarkBadges';
import { PolicyAuthorityPill } from '../../trust/PolicyAuthorityPill/PolicyAuthorityPill';
import { ChannelLogo } from '../ChannelLogo/ChannelLogo';
import shared from '../../../styles/shared.module.css';
import styles from './CommandCenterSubcomponents.module.css';

const TRUST_PILL_PROPS = COMMAND_CENTER_POLICY_CHIP_PROPS;

const DISCREPANCY_TIER_CLASS: Record<ReturnType<typeof discrepancyRateTier>, string> = {
  green: styles.discrepancyTierGreen,
  amber: styles.discrepancyTierAmber,
  red: styles.discrepancyTierRed,
  unavailable: styles.discrepancyTierUnavailable,
};

export function ChannelTrustGroupByToggle({
  groupBy,
  onChange,
}: {
  groupBy: ChannelTrustGroupBy;
  onChange: (next: ChannelTrustGroupBy) => void;
}) {
  const copy = COMMAND_CENTER_COPY.channelTrustGroupBy;
  const options: Array<{ id: ChannelTrustGroupBy; label: string }> = [
    { id: 'platform', label: copy.platform },
    { id: 'campaign_class', label: copy.campaignClass },
    { id: 'commerce_rail', label: copy.commerceRail },
  ];

  return (
    <div
      className={styles.channelTrustGroupBy}
      role="radiogroup"
      aria-label={copy.groupLabel}
      data-channel-trust-group-by
    >
      {options.map((option) => (
        <button
          key={option.id}
          type="button"
          role="radio"
          aria-checked={groupBy === option.id}
          className={[
            styles.channelTrustGroupByButton,
            groupBy === option.id ? styles.channelTrustGroupByButtonActive : '',
          ].join(' ')}
          onClick={() => onChange(option.id)}
          data-channel-trust-group-by-option={option.id}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export function ChannelTrustAxisCell({
  row,
  groupBy,
  rowNavigateViaRow = false,
}: {
  row: ChannelTrustRow;
  groupBy: ChannelTrustGroupBy;
  rowNavigateViaRow?: boolean;
}) {
  const label = resolveAxisLabel(row, groupBy);
  const logoVisible = showPlatformLogo(groupBy);

  return (
    <div className={styles.channelIdentity}>
      {logoVisible ? (
        <ChannelLogo claimSource={row.claimSource} />
      ) : (
        <span className={styles.channelAxisLogoSpacer} aria-hidden="true" />
      )}
      {row.detailHref && groupBy === 'platform' && !rowNavigateViaRow ? (
        <Link
          to={row.detailHref}
          className={[styles.channelLink, styles.channelName].join(' ')}
          data-channel-reconstruction-link={row.channelId}
          title={`${label} — open channel record`}
        >
          {label}
        </Link>
      ) : (
        <span
          className={[styles.channelName, styles.channelAxisLabel].join(' ')}
          data-channel-reconstruction-link={rowNavigateViaRow ? row.channelId : undefined}
          data-channel-trust-axis-label={row.rowId}
          title={label}
        >
          {label}
        </span>
      )}
    </div>
  );
}

export function ChannelTrustInteractiveRow({
  row,
  groupBy,
  children,
}: {
  row: ChannelTrustRow;
  groupBy: ChannelTrustGroupBy;
  children: ReactNode;
}) {
  const navigate = useNavigate();
  const interactive = Boolean(row.detailHref && groupBy === 'platform');

  if (!interactive) {
    return <tr data-channel-trust-row={row.channelId}>{children}</tr>;
  }

  const activate = () => {
    navigate(row.detailHref!, { state: { fromCommandCenterChannelTrust: true } });
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTableRowElement>) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      activate();
    }
  };

  return (
    <tr
      data-channel-trust-row={row.channelId}
      data-table-row-interactive
      data-channel-trust-row-link={row.channelId}
      className={[styles.channelTrustInteractiveRow, shared.focusVisible].join(' ')}
      tabIndex={0}
      role="link"
      aria-label={`${resolveAxisLabel(row, groupBy)} — open channel record`}
      onClick={activate}
      onKeyDown={onKeyDown}
    >
      {children}
    </tr>
  );
}

export function ChannelTrustVerifiedRevenueCell({ row }: { row: ChannelTrustRow }) {
  return (
    <span
      className={styles.moneyStrong}
      title={verifiedRevenueMinorTitle(row.verifiedRevenueMinor, row.currencyCode)}
      data-verified-revenue-minor={row.verifiedRevenueMinor.toString()}
    >
      {formatMoneyMinorDisplay(row.verifiedRevenueMinor, row.currencyCode)}
    </span>
  );
}

export function ChannelTrustDiscrepancyCell({ row }: { row: ChannelTrustRow }) {
  const tier = discrepancyRateTier(row.discrepancyRateBps);
  return (
    <span
      className={[styles.discrepancyValue, DISCREPANCY_TIER_CLASS[tier]].join(' ')}
      data-channel-trust-discrepancy-tier={tier}
      data-discrepancy-rate={row.discrepancyRateBps ?? 'na'}
    >
      {formatChannelDiscrepancyRate(row.discrepancyRateBps)}
    </span>
  );
}

export function ChannelTrustRevenueReliabilityCell({ row }: { row: ChannelTrustRow }) {
  const resolution = resolveRevenueReliabilityFromTier(row.modelAgreementTier);
  return (
    <RevenueReliabilityBadge
      state={resolution.state}
      invalid={resolution.invalid}
      data-model-agreement-tier={row.modelAgreementTier}
    />
  );
}

export function ChannelTrustPolicyCell({ row }: { row: ChannelTrustRow }) {
  return (
    <div className={styles.channelTrustWrapCell}>
      <PolicyAuthorityPill state={row.policyAuthority} {...TRUST_PILL_PROPS} appearance="text" />
    </div>
  );
}

export function ChannelTrustBenchmarkCell({ row }: { row: ChannelTrustRow }) {
  const title = benchmarkCellTitle(row.benchmarkEvidenceClass, row.benchmarkUnavailableReason);
  return (
    <div
      className={styles.channelTrustWrapCell}
      title={title}
      data-channel-trust-benchmark={row.rowId}
    >
      {row.benchmarkValue ? (
        <span className={styles.benchmarkValue} data-benchmark-value>
          {row.benchmarkValue}
        </span>
      ) : null}
      <EvidenceClassBadge value={row.benchmarkEvidenceClass} variant="text" />
    </div>
  );
}
