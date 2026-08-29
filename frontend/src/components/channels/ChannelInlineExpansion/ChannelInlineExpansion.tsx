import { Link } from 'react-router-dom';
import type { ChannelOverviewRowDTO } from '../../../ledger/types';
import { formatMoneyMinorDisplay, formatBpsAsPercentOneDecimal } from '../../../lib/money';
import { CHANNEL_INLINE_COPY } from '../../../channels/channelInlineCopy';
import {
  channelBenchmarkSentence,
  channelDiscrepancyMinor,
  channelReliabilityExplanation,
  channelReliabilityLabel,
  resolveChannelDataReliability,
  type ChannelDataReliability,
} from '../../../channels/channelInlineDisplay';
import { getChannelInlineExpansionFixture } from '../../../channels/channelInlineFixtures';
import { channelsClaimSourceLabel } from '../../../channels/channelsDisplay';
import {
  COMMAND_CENTER_CHIP_PROPS,
  COMMAND_CENTER_POLICY_CHIP_PROPS,
} from '../../../commandCenter/commandCenterChipProps';
import { AuthorityBadge } from '../../trust/AuthorityBadge/AuthorityBadge';
import { PolicyAuthorityPill } from '../../trust/PolicyAuthorityPill/PolicyAuthorityPill';
import { TrustChip, type TrustChipTone } from '../../trust/TrustChip/TrustChip';
import { DiscrepancyBadge } from '../../commandCenter/StatusBadges/StatusBadges';
import { ErrorBanner } from '../../layout/ErrorBanner/ErrorBanner';
import { Skeleton } from '../../layout/Skeleton/Skeleton';
import shared from '../../../styles/shared.module.css';
import { ChannelVerifiedTrendBars } from './ChannelVerifiedTrendBars';
import styles from './ChannelInlineExpansion.module.css';

export type ChannelInlineExpansionState = 'loaded' | 'loading' | 'error';

export interface ChannelInlineExpansionProps {
  row: ChannelOverviewRowDTO;
  /** Fail-closed expansion state. Defaults to loaded. */
  expansionState?: ChannelInlineExpansionState;
  onRetry?: () => void;
}

const RELIABILITY_TONE: Record<ChannelDataReliability, TrustChipTone> = {
  verified: 'deterministic',
  estimated: 'warning',
  pending: 'neutral',
};

/** Table-chip casing — matches AuthorityBadge `size="table"`. */
const RELIABILITY_CHIP_LABEL: Record<ChannelDataReliability, string> = {
  verified: 'verified',
  estimated: 'estimated',
  pending: 'pending',
};

function ReliabilityChip({ reliability }: { reliability: ChannelDataReliability }) {
  const label = channelReliabilityLabel(reliability);
  return (
    <TrustChip
      tone={RELIABILITY_TONE[reliability]}
      data-channel-reliability={reliability}
      title={CHANNEL_INLINE_COPY.reliability.tooltip(label)}
      aria-label={`${CHANNEL_INLINE_COPY.reliability.label}: ${label}. ${channelReliabilityExplanation(reliability)}`}
    >
      {RELIABILITY_CHIP_LABEL[reliability]}
    </TrustChip>
  );
}

function differenceValueClass(
  status: ChannelOverviewRowDTO['discrepancyStatus'],
  discrepancyClass: ChannelOverviewRowDTO['discrepancyClass'],
): string {
  if (discrepancyClass === 'material') return styles.moneyValueError;
  if (status === 'flagged' || status === 'rejected') return styles.moneyValueWarning;
  return '';
}

function differenceMetaClass(
  status: ChannelOverviewRowDTO['discrepancyStatus'],
  discrepancyClass: ChannelOverviewRowDTO['discrepancyClass'],
): string {
  if (discrepancyClass === 'material') return styles.moneyMetaError;
  if (status === 'flagged' || status === 'rejected') return styles.moneyMetaWarning;
  if (status === 'unavailable') return '';
  return styles.moneyMetaSuccess;
}

export function ChannelInlineExpansion({
  row,
  expansionState = 'loaded',
  onRetry,
}: ChannelInlineExpansionProps) {
  const reliability = resolveChannelDataReliability(row);
  const holdReasonId = `channel-hold-reason-${row.channelId}`;
  const claimsHref = `/app/claims?claimSource=${encodeURIComponent(row.claimSource)}`;
  const holdEnabled =
    row.policyAuthority === 'approval_required' ||
    row.policyAuthority === 'proposal_required' ||
    row.policyAuthority === 'simulation_only';
  const holdReason =
    row.policyAuthority === 'blocked'
      ? CHANNEL_INLINE_COPY.actions.holdBlockedPolicy
      : CHANNEL_INLINE_COPY.actions.holdBlockedTooltip;
  const showPlatformWarning = row.discrepancyClass === 'material';
  const claimedCrossed = row.discrepancyClass === 'material';

  if (expansionState === 'loading') {
    return (
      <aside
        className={styles.panel}
        data-channel-inline-expansion={row.channelId}
        data-channel-inline-state="loading"
        aria-busy="true"
        aria-label={`${row.channelName} channel defense summary`}
      >
        <Skeleton rows={3} variant="row" />
        <p className={styles.loadingCopy} role="status" aria-live="polite">
          {CHANNEL_INLINE_COPY.loading.progress}
        </p>
      </aside>
    );
  }

  if (expansionState === 'error') {
    return (
      <aside
        className={styles.panel}
        data-channel-inline-expansion={row.channelId}
        data-channel-inline-state="error"
        aria-label={`${row.channelName} channel defense summary`}
      >
        <ErrorBanner variant="error" message={CHANNEL_INLINE_COPY.error.message} />
        {onRetry ? (
          <button
            type="button"
            className={[styles.secondaryAction, shared.focusVisible].join(' ')}
            onClick={onRetry}
            data-channel-inline-retry
          >
            Retry
          </button>
        ) : null}
      </aside>
    );
  }

  const fixture = getChannelInlineExpansionFixture(row.channelId);
  const differenceMinor = channelDiscrepancyMinor(row);
  const claimedDisplay = formatMoneyMinorDisplay(row.claimedRevenueMinor, row.currencyCode);
  const verifiedDisplay = formatMoneyMinorDisplay(row.verifiedRevenueMinor, row.currencyCode);
  const differenceDisplay = formatMoneyMinorDisplay(differenceMinor, row.currencyCode);

  return (
    <aside
      className={styles.panel}
      data-channel-inline-expansion={row.channelId}
      data-channel-inline-state="loaded"
      aria-label={`${row.channelName} channel defense summary`}
    >
      {/* Deck 1 — Defense (hierarchy rank 1–2) */}
      <div className={styles.defenseDeck} data-channel-inline-deck="defense">
        <header className={styles.header}>
          <div className={styles.identity}>
            <p className={styles.channelName} data-channel-inline-name>
              {row.channelName}
            </p>
            <p className={styles.platformLine} data-channel-inline-platform>
              {channelsClaimSourceLabel(row.claimSource)}
            </p>
          </div>
          <ReliabilityChip reliability={reliability} />
        </header>

        <div className={styles.defenseBody}>
          <section
            className={styles.moneyStrip}
            data-channel-inline-section="revenue"
            aria-label="Channel revenue defense"
          >
            <article className={styles.moneyCard} data-channel-money="verified">
              <div className={styles.moneyBody}>
                <div className={styles.moneyTopRow}>
                  <span className={styles.moneyLabel}>{CHANNEL_INLINE_COPY.revenue.verified}</span>
                  <span className={styles.moneyChip}>
                    <AuthorityBadge authority="deterministic" {...COMMAND_CENTER_CHIP_PROPS} />
                  </span>
                </div>
                <span
                  className={styles.moneyValue}
                  data-channel-inline-verified
                  title={`${row.verifiedRevenueMinor.toString()} minor units`}
                >
                  {verifiedDisplay}
                </span>
                <span className={[styles.moneyMeta, styles.moneyMetaSuccess].join(' ')}>
                  {CHANNEL_INLINE_COPY.revenue.verifiedMeta}
                </span>
              </div>
            </article>
            <article className={styles.moneyCard} data-channel-money="claimed">
              <div className={styles.moneyBody}>
                <span className={styles.moneyLabel}>{CHANNEL_INLINE_COPY.revenue.claimed}</span>
                <span
                  className={[
                    styles.moneyValue,
                    claimedCrossed ? styles.moneyValueCrossed : '',
                  ]
                    .filter(Boolean)
                    .join(' ')}
                  data-channel-inline-claimed
                  title={`${row.claimedRevenueMinor.toString()} minor units`}
                >
                  {claimedDisplay}
                </span>
                <span
                  className={[
                    styles.moneyMeta,
                    claimedCrossed ? styles.moneyMetaWarning : '',
                  ]
                    .filter(Boolean)
                    .join(' ')}
                >
                  {claimedCrossed
                    ? CHANNEL_INLINE_COPY.revenue.claimedMetaCrossed
                    : CHANNEL_INLINE_COPY.revenue.claimedMeta}
                </span>
              </div>
            </article>
            <article className={styles.moneyCard} data-channel-money="difference">
              <div className={styles.moneyBody}>
                <span className={styles.moneyLabel}>{CHANNEL_INLINE_COPY.revenue.difference}</span>
                <span
                  className={[
                    styles.moneyValue,
                    differenceValueClass(row.discrepancyStatus, row.discrepancyClass),
                  ]
                    .filter(Boolean)
                    .join(' ')}
                  data-channel-inline-difference
                  title={`${differenceMinor.toString()} minor units`}
                >
                  {differenceDisplay}
                </span>
                <span
                  className={[
                    styles.moneyMeta,
                    differenceMetaClass(row.discrepancyStatus, row.discrepancyClass),
                  ]
                    .filter(Boolean)
                    .join(' ')}
                  data-channel-inline-discrepancy
                >
                  <DiscrepancyBadge status={row.discrepancyStatus} table variant="text" />
                </span>
              </div>
            </article>
          </section>

          <section className={styles.actionBar} data-channel-inline-section="actions">
            <div className={styles.policyRow}>
              <PolicyAuthorityPill
                state={row.policyAuthority}
                {...COMMAND_CENTER_POLICY_CHIP_PROPS}
                appearance="text"
              />
            </div>
            <div className={styles.actionRow}>
              <Link
                to={claimsHref}
                className={[styles.reviewAction, shared.focusVisible].join(' ')}
                data-channel-inline-review
                data-channel-inline-claims-link
              >
                {CHANNEL_INLINE_COPY.actions.reviewClaimsWithCount(row.relatedClaimsCount)}
              </Link>
              <button
                type="button"
                className={[styles.secondaryAction, shared.focusVisible].join(' ')}
                disabled={!holdEnabled}
                title={!holdEnabled ? holdReason : undefined}
                aria-disabled={!holdEnabled}
                aria-describedby={!holdEnabled ? holdReasonId : undefined}
                data-channel-inline-hold
              >
                {CHANNEL_INLINE_COPY.actions.holdSpend}
              </button>
            </div>
            {!holdEnabled ? (
              <p id={holdReasonId} className={styles.holdReason} data-channel-hold-reason role="status">
                {holdReason}
              </p>
            ) : null}
          </section>
        </div>

        {showPlatformWarning ? (
          <p className={styles.platformWarning} role="status" data-channel-inline-platform-warning>
            {CHANNEL_INLINE_COPY.platformWarning}
          </p>
        ) : null}
      </div>

      {/* Deck 2 — Levers */}
      <div className={styles.leversDeck} data-channel-inline-deck="levers">
        <section className={styles.campaignsBlock} data-channel-inline-section="campaigns">
          <h3 className={styles.deckLabel}>{CHANNEL_INLINE_COPY.campaigns.sectionLabel}</h3>
          {fixture.campaigns.length === 0 ? (
            <p className={styles.emptyLine}>{CHANNEL_INLINE_COPY.campaigns.empty}</p>
          ) : (
            <table className={styles.campaignTable} data-channel-inline-campaigns>
              <caption className={shared.srOnly}>{CHANNEL_INLINE_COPY.campaigns.sectionLabel}</caption>
              <thead>
                <tr>
                  <th scope="col">{CHANNEL_INLINE_COPY.campaigns.columns.name}</th>
                  <th scope="col">{CHANNEL_INLINE_COPY.campaigns.columns.verified}</th>
                  <th scope="col">{CHANNEL_INLINE_COPY.campaigns.columns.share}</th>
                </tr>
              </thead>
              <tbody>
                {fixture.campaigns.map((campaign) => (
                  <tr key={campaign.campaignId} data-channel-campaign-row={campaign.campaignId}>
                    <td>{campaign.campaignName}</td>
                    <td title={`${campaign.verifiedRevenueMinor.toString()} minor units`}>
                      {formatMoneyMinorDisplay(campaign.verifiedRevenueMinor, row.currencyCode)}
                    </td>
                    <td>{formatBpsAsPercentOneDecimal(campaign.shareBps)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className={styles.trendBlock} data-channel-inline-section="trend">
          <h3 className={styles.deckLabel}>{CHANNEL_INLINE_COPY.trend.sectionLabel}</h3>
          <ChannelVerifiedTrendBars points={fixture.trend} currencyCode={row.currencyCode} />
        </section>
      </div>

      {/* Deck 3 — Context (one line, not competing sections) */}
      <p className={styles.contextRow} data-channel-inline-deck="context">
        <span data-channel-inline-model>{CHANNEL_INLINE_COPY.attribution.modelLine}</span>
        <span className={styles.contextSep} aria-hidden>
          ·
        </span>
        <span data-channel-inline-benchmark>{channelBenchmarkSentence(row)}</span>
      </p>
    </aside>
  );
}
