import { Link } from 'react-router-dom';
import type { ClaimJourneyOriginRow, ClaimPaidAttributionRow } from '../../../detail/types';
import { CLAIM_DETAIL_COPY } from '../../../claims/claimDetailCopy';
import {
  attributionModelLabel,
  formatMoneyMinorDisplay,
  formatPaidPlatformClassLabel,
  formatShareOfVerified,
} from '../../../claims/claimDetailDisplay';
import { commerceRailLabel } from '../../../claims/claimsLedgerDisplay';
import { buildChannelExpandHref } from '../../../channels/channelExpandHref';
import shared from '../../../styles/shared.module.css';
import styles from './AttributionBreakdownPanel.module.css';
import pageStyles from './ClaimDetailPage.module.css';

export interface AttributionBreakdownPanelProps {
  claimSource: string;
  claimedRevenueMinor: bigint;
  currencyCode: string;
  defaultModel: string;
  paidAttribution: ClaimPaidAttributionRow[];
  journeyOrigins: ClaimJourneyOriginRow[];
}

function rankByAmountDesc<T extends { amountMinor: bigint }>(rows: T[]): T[] {
  return [...rows].sort((a, b) => {
    if (b.amountMinor === a.amountMinor) return 0;
    return b.amountMinor > a.amountMinor ? 1 : -1;
  });
}

export function AttributionBreakdownPanel({
  currencyCode,
  defaultModel,
  paidAttribution,
  journeyOrigins,
}: AttributionBreakdownPanelProps) {
  const paidRanked = rankByAmountDesc(paidAttribution);
  const journeyRanked = rankByAmountDesc(journeyOrigins);
  const paidTotal = paidRanked.reduce((sum, row) => sum + row.amountMinor, 0n);
  const modelPlain = attributionModelLabel(defaultModel);

  if (paidRanked.length === 0 && journeyRanked.length === 0) {
    return (
      <section
        className={[pageStyles.cardSection, styles.enter].join(' ')}
        aria-label={CLAIM_DETAIL_COPY.attribution.paidHeading}
        data-claim-attribution-section
        data-claim-attribution-breakdown
        data-claim-attribution-model={modelPlain}
      >
        <header className={pageStyles.cardHeader}>
          <h2 className={pageStyles.cardTitle}>{CLAIM_DETAIL_COPY.attribution.paidHeading}</h2>
        </header>
        <p className={styles.empty} role="status">
          {CLAIM_DETAIL_COPY.attribution.empty}
        </p>
      </section>
    );
  }

  return (
    <section
      className={[pageStyles.cardSection, styles.enter].join(' ')}
      aria-label={CLAIM_DETAIL_COPY.attribution.paidHeading}
      data-claim-attribution-section
      data-claim-attribution-breakdown
      data-claim-attribution-model={modelPlain}
    >
      <header className={pageStyles.cardHeader}>
        <h2 className={pageStyles.cardTitle}>{CLAIM_DETAIL_COPY.attribution.paidHeading}</h2>
      </header>
      <div className={styles.tier} data-claim-paid-attribution>
        {paidRanked.length === 0 ? (
          <p className={styles.empty} role="status">
            {CLAIM_DETAIL_COPY.attribution.paidEmpty}
          </p>
        ) : (
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">{CLAIM_DETAIL_COPY.attribution.paidPlatformClass}</th>
                <th scope="col">{CLAIM_DETAIL_COPY.attribution.paidRevenue}</th>
                <th scope="col">{CLAIM_DETAIL_COPY.attribution.paidShare}</th>
              </tr>
            </thead>
            <tbody>
              {paidRanked.map((row) => {
                const label = formatPaidPlatformClassLabel(row.platform, row.campaignClass);
                return (
                  <tr
                    key={row.channelId}
                    data-claim-paid-row={row.channelId}
                    data-claim-attribution-row={row.channelId}
                  >
                    <td>
                      <Link
                        to={buildChannelExpandHref(row.channelId)}
                        className={[styles.rowLink, shared.focusVisible].join(' ')}
                        data-claim-paid-channel-link={row.channelId}
                      >
                        {label}
                      </Link>
                    </td>
                    <td className={styles.numeric}>
                      {formatMoneyMinorDisplay(row.amountMinor, currencyCode)}
                    </td>
                    <td className={styles.numeric}>
                      {formatShareOfVerified(row.amountMinor, paidTotal)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      <div className={styles.tier} data-claim-journey-origins>
        <h2 className={styles.tierHeading}>{CLAIM_DETAIL_COPY.attribution.journeyHeading}</h2>
        {journeyRanked.length === 0 ? (
          <p className={styles.empty} role="status">
            {CLAIM_DETAIL_COPY.attribution.journeyEmpty}
          </p>
        ) : (
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">{CLAIM_DETAIL_COPY.attribution.journeyRail}</th>
                <th scope="col">{CLAIM_DETAIL_COPY.attribution.journeyRevenue}</th>
              </tr>
            </thead>
            <tbody>
              {journeyRanked.map((row) => (
                <tr key={row.commerceRail} data-claim-journey-row={row.commerceRail}>
                  <td>{commerceRailLabel(row.commerceRail)}</td>
                  <td className={styles.numeric}>
                    {formatMoneyMinorDisplay(row.amountMinor, currencyCode)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
