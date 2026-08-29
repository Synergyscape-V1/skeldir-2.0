import { Link, useInRouterContext, useLocation } from 'react-router-dom';
import { SUPERVISORY_TABLE_STATUS_TEXT, COMMAND_CENTER_POLICY_CHIP_PROPS } from '../../../commandCenter/commandCenterChipProps';
import { ChannelLogo } from '../../commandCenter/ChannelLogo/ChannelLogo';
import { MatchVerdictBadge } from '../../commandCenter/StatusBadges/StatusBadges';
import { PolicyAuthorityPill } from '../../trust/PolicyAuthorityPill/PolicyAuthorityPill';
import { AuthorityBadge } from '../../trust/AuthorityBadge/AuthorityBadge';
import { ExecutiveReliabilityBadge } from '../../trust/ExecutiveReliabilityBadge/ExecutiveReliabilityBadge';
import {
  campaignClassLabel,
  claimSourceLabel,
  commerceRailLabel,
  formatClaimTimeUtcDate,
} from '../../../claims/claimsLedgerDisplay';
import { resolveClaimsConfidenceLedgerProjection } from '../../../claims/confidenceLedgerDisplay';
import { PRODUCT_TABLE_CHIP_PROPS } from '../../../commandCenter/commandCenterChipProps';
import { DiscrepancyIndicator } from '../../trust/DiscrepancyIndicator/DiscrepancyIndicator';
import { formatMoneyMinorDisplay } from '../../../lib/money';
import { resolveClaimLedgerExecutiveReliability } from '../../../trust/executiveDataReliability';
import type { ClaimLedgerRowDTO, ConfidenceShape } from '../../../ledger/types';
import shared from '../../../styles/shared.module.css';
import styles from './ClaimsLedgerTableCells.module.css';

export function ClaimTimeCell({ row }: { row: ClaimLedgerRowDTO }) {
  const dateLabel = formatClaimTimeUtcDate(row.claimTime);

  if (!dateLabel) {
    return (
      <time className={styles.claimTime} dateTime={row.claimTime}>
        Invalid claim time
      </time>
    );
  }

  return (
    <time className={styles.claimTime} dateTime={row.claimTime}>
      {dateLabel}
    </time>
  );
}

export function ClaimPlatformSourceCell({ row }: { row: ClaimLedgerRowDTO }) {
  const sourceLabel = claimSourceLabel(row.claimSource);

  return (
    <div className={styles.platformSourceCell} data-claim-source-cell={row.claimSource}>
      <ChannelLogo claimSource={row.claimSource} />
      <span className={styles.dimensionLabel} data-claim-platform-name title={sourceLabel}>
        {sourceLabel}
      </span>
    </div>
  );
}

export function CampaignClassCell({ row }: { row: ClaimLedgerRowDTO }) {
  const label = campaignClassLabel(row.campaignClass);
  return (
    <span
      className={styles.dimensionLabel}
      data-campaign-class={row.campaignClass}
      title={label}
    >
      {label}
    </span>
  );
}

export function CommerceRailCell({ row }: { row: ClaimLedgerRowDTO }) {
  const label = commerceRailLabel(row.commerceRail);
  return (
    <span className={styles.dimensionLabel} data-commerce-rail={row.commerceRail} title={label}>
      {label}
    </span>
  );
}

/** @deprecated Use ClaimPlatformSourceCell */
export function ClaimSourceCell({ row }: { row: ClaimLedgerRowDTO }) {
  return <ClaimPlatformSourceCell row={row} />;
}

export function ClaimedRevenueCell({ row }: { row: ClaimLedgerRowDTO }) {
  return (
    <span
      className={styles.moneyAmount}
      data-claimed-revenue-minor={row.claimedRevenueMinor.toString()}
      title={`${row.claimedRevenueMinor.toString()} minor units`}
    >
      {formatMoneyMinorDisplay(row.claimedRevenueMinor, row.currencyCode)}
    </span>
  );
}

export function VerifiedRevenueCell({ row }: { row: ClaimLedgerRowDTO }) {
  const reliability = resolveClaimLedgerExecutiveReliability({
    matchVerdict: row.matchVerdict,
    confidence: row.confidence,
    verificationStatus: row.verificationStatus,
    discrepancyClass: row.discrepancyClass,
  });

  return (
    <div className={styles.verifiedRevenueCell} data-verified-revenue-cell>
      <span
        className={styles.moneyAmount}
        data-verified-revenue-minor={row.verifiedRevenueMinor.toString()}
        title={`${row.verifiedRevenueMinor.toString()} minor units`}
      >
        {formatMoneyMinorDisplay(row.verifiedRevenueMinor, row.currencyCode)}
      </span>
      <ExecutiveReliabilityBadge
        reliability={reliability.reliability}
        variant={reliability.variant}
        showIcon={false}
      />
    </div>
  );
}

export function DifferenceCell({ row }: { row: ClaimLedgerRowDTO }) {
  return (
    <DiscrepancyIndicator
      claimedRevenueMinor={row.claimedRevenueMinor}
      verifiedRevenueMinor={row.verifiedRevenueMinor}
      discrepancyAmountMinor={row.discrepancyAmountMinor}
      discrepancyRateBps={row.discrepancyRateBps}
      discrepancyClass={row.discrepancyClass}
      currencyCode={row.currencyCode}
      variant="table"
    />
  );
}

export function MatchVerdictCell({ row }: { row: ClaimLedgerRowDTO }) {
  return (
    <MatchVerdictBadge
      status={row.matchVerdict}
      discrepancyClass={row.discrepancyClass}
      {...SUPERVISORY_TABLE_STATUS_TEXT}
    />
  );
}

export function AttributionModelCell({ row }: { row: ClaimLedgerRowDTO }) {
  return (
    <span className={styles.truncatedMetaText} data-attribution-model={row.attributionModel} title={row.attributionModel}>
      {row.attributionModel}
    </span>
  );
}

const CONFIDENCE_COLOR_CLASS: Record<
  ReturnType<typeof resolveClaimsConfidenceLedgerProjection>['colorTone'],
  string
> = {
  success: styles.confidenceTextSuccess,
  probabilistic: styles.confidenceTextProbabilistic,
  info: styles.confidenceTextInfo,
  warning: styles.confidenceTextWarning,
  error: styles.confidenceTextError,
  neutral: styles.confidenceTextNeutral,
};

const AVAILABLE_INTERVAL_DISPOSITIONS = new Set([
  'available_exact',
  'available_stable',
  'available_wide',
]);

export function ClaimsLedgerConfidenceCell({ confidence }: { confidence: ConfidenceShape }) {
  const projection = resolveClaimsConfidenceLedgerProjection(confidence);
  const showProbabilisticAuthority = AVAILABLE_INTERVAL_DISPOSITIONS.has(projection.disposition);

  if (showProbabilisticAuthority) {
    return (
      <div
        className={styles.confidenceCell}
        data-claims-confidence-cell
        data-claims-confidence-disposition={projection.disposition}
        data-claims-confidence-color-tone={projection.colorTone}
        data-claims-confidence-authority="probabilistic"
        title={projection.title}
      >
        <span className={styles.confidenceInterval}>{projection.shortLabel}</span>
        <AuthorityBadge authority="probabilistic" {...PRODUCT_TABLE_CHIP_PROPS} />
      </div>
    );
  }

  return (
    <span
      className={CONFIDENCE_COLOR_CLASS[projection.colorTone]}
      data-claims-confidence-cell
      data-claims-confidence-disposition={projection.disposition}
      data-claims-confidence-color-tone={projection.colorTone}
      title={projection.title}
    >
      {projection.shortLabel}
    </span>
  );
}

export function PolicyAuthorityCell({ row }: { row: ClaimLedgerRowDTO }) {
  return (
    <PolicyAuthorityPill
      state={row.policyAuthority}
      {...COMMAND_CENTER_POLICY_CHIP_PROPS}
      appearance="text"
    />
  );
}

function AuditOpenLink({
  row,
  detailPath,
}: {
  row: ClaimLedgerRowDTO;
  detailPath: string;
}) {
  const location = useLocation();

  return (
    <Link
      to={detailPath}
      state={{ parentSearch: location.search }}
      className={[styles.openButton, shared.focusVisible].join(' ')}
      data-audit-open-affordance="navigate"
      aria-label={`Open claim record for ${row.claimRef}`}
    >
      Open
    </Link>
  );
}

export function AuditOpenCell({ row, disabled }: { row: ClaimLedgerRowDTO; disabled?: boolean }) {
  const detailPath = `/app/claims/${row.claimRef}`;
  const inRouter = useInRouterContext();

  if (disabled) {
    return (
      <button
        type="button"
        className={styles.openButton}
        disabled
        data-audit-open-affordance="navigate"
        aria-label={`Open claim record for ${row.claimRef}`}
      >
        Open
      </button>
    );
  }

  if (inRouter) {
    return <AuditOpenLink row={row} detailPath={detailPath} />;
  }

  return (
    <a
      href={detailPath}
      className={[styles.openButton, shared.focusVisible].join(' ')}
      data-audit-open-affordance="navigate"
      aria-label={`Open claim record for ${row.claimRef}`}
    >
      Open
    </a>
  );
}
