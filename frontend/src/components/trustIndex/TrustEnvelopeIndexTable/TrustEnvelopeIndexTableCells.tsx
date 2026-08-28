import { Link, useInRouterContext, useLocation } from 'react-router-dom';
import { TRUST_INDEX_AUTHORITY_CHIP, TRUST_INDEX_POLICY_CHIP } from '../../../commandCenter/commandCenterChipProps';
import { ChannelLogo } from '../../commandCenter/ChannelLogo/ChannelLogo';
import { DiscrepancyIndicator } from '../../trust/DiscrepancyIndicator/DiscrepancyIndicator';
import { AuthorityBadge } from '../../trust/AuthorityBadge/AuthorityBadge';
import { ExecutiveReliabilityBadge } from '../../trust/ExecutiveReliabilityBadge/ExecutiveReliabilityBadge';
import { PolicyAuthorityPill } from '../../trust/PolicyAuthorityPill/PolicyAuthorityPill';
import { buildTrustEnvelopeAuditReferenceHref } from '../../../detail/auditReference';
import { formatClaimTimeUtcDate } from '../../../claims/claimsLedgerDisplay';
import { formatMoneyMinorDisplay } from '../../../lib/money';
import { resolveTrustIndexExecutiveReliability } from '../../../trust/executiveDataReliability';
import type { TrustEnvelopeIndexRowDTO } from '../../../ledger/types';
import {
  confidenceUnavailableReason,
  formatMatchVerdictLabel,
  formatTrustIndexClaimSourceLabel,
  TRUST_INDEX_ATTRIBUTION_DISCLAIMER,
} from '../../../trustIndex/trustIndexEnvelopeDisplay';
import { TRUST_ENVELOPE_INDEX_COPY } from '../../../trustIndex/copy';
import shared from '../../../styles/shared.module.css';
import styles from './TrustEnvelopeIndexTableCells.module.css';

export function TrustIndexClaimTimeCell({ row }: { row: TrustEnvelopeIndexRowDTO }) {
  const dateLabel = formatClaimTimeUtcDate(row.claimTime);
  if (!dateLabel) {
    return (
      <time dateTime={row.claimTime} data-trust-index-claim-time={row.envelopeId}>
        Invalid claim time
      </time>
    );
  }
  return (
    <time
      className={styles.claimTime}
      dateTime={row.claimTime}
      data-trust-index-claim-time={row.envelopeId}
    >
      {dateLabel}
    </time>
  );
}

export function TrustIndexClaimSourceCell({ row }: { row: TrustEnvelopeIndexRowDTO }) {
  const label = formatTrustIndexClaimSourceLabel(row.claimSource);

  return (
    <div
      className={styles.claimSourceCell}
      data-trust-index-claim-source={row.envelopeId}
      data-claim-source={row.claimSource}
    >
      <ChannelLogo claimSource={row.claimSource} />
      <span className={styles.dimensionLabel} title={row.claimSource}>
        {label}
      </span>
    </div>
  );
}

export function TrustIndexClaimedRevenueCell({ row }: { row: TrustEnvelopeIndexRowDTO }) {
  return (
    <span
      className={styles.moneyStrong}
      data-trust-index-claimed-revenue={row.envelopeId}
      data-claimed-revenue-minor={row.claimedRevenueMinor.toString()}
      title={`${row.claimedRevenueMinor.toString()} minor units`}
    >
      {formatMoneyMinorDisplay(row.claimedRevenueMinor, row.currencyCode)}
    </span>
  );
}

export function TrustIndexVerifiedRevenueCell({ row }: { row: TrustEnvelopeIndexRowDTO }) {
  const reliability = resolveTrustIndexExecutiveReliability({
    matchVerdict: row.matchVerdict,
    confidence: row.confidence,
    verificationStatus: row.verificationStatus,
    discrepancyClass: row.discrepancyClass,
  });

  return (
    <div className={styles.verifiedRevenueCell} data-trust-index-verified-revenue-wrap={row.envelopeId}>
      <span
        className={styles.moneyStrong}
        data-trust-index-verified-revenue={row.envelopeId}
        data-verified-revenue-minor={row.verifiedRevenueMinor.toString()}
        title={`verifiedRevenueMinor: ${row.verifiedRevenueMinor.toString()}`}
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

export function TrustIndexDifferenceCell({ row }: { row: TrustEnvelopeIndexRowDTO }) {
  return (
    <div data-trust-index-difference={row.envelopeId}>
      <DiscrepancyIndicator
        claimedRevenueMinor={row.claimedRevenueMinor}
        verifiedRevenueMinor={row.verifiedRevenueMinor}
        discrepancyAmountMinor={row.discrepancyAmountMinor}
        discrepancyRateBps={row.discrepancyRateBps}
        discrepancyClass={row.discrepancyClass}
        currencyCode={row.currencyCode}
        variant="table"
      />
    </div>
  );
}

export function TrustIndexMatchVerdictCell({ row }: { row: TrustEnvelopeIndexRowDTO }) {
  return (
    <code
      className={styles.matchVerdict}
      data-trust-index-match-verdict={row.envelopeId}
      data-match-verdict={row.matchVerdict}
    >
      {formatMatchVerdictLabel(row.matchVerdict)}
    </code>
  );
}

export function TrustIndexAttributionModelCell({ row }: { row: TrustEnvelopeIndexRowDTO }) {
  return (
    <span
      className={styles.truncatedMetaText}
      data-trust-index-attribution={row.envelopeId}
      title={TRUST_INDEX_ATTRIBUTION_DISCLAIMER}
    >
      {row.attributionModel}
    </span>
  );
}

export function TrustIndexConfidenceCell({ row }: { row: TrustEnvelopeIndexRowDTO }) {
  if (row.confidence.status === 'available') {
    return (
      <div className={styles.confidenceCell} data-trust-index-confidence={row.envelopeId}>
        <AuthorityBadge authority="probabilistic" {...TRUST_INDEX_AUTHORITY_CHIP} />
      </div>
    );
  }

  const reason = confidenceUnavailableReason(row.confidence);
  return (
    <div className={styles.confidenceCell} data-trust-index-confidence={row.envelopeId} title={reason}>
      <AuthorityBadge authority="unavailable" {...TRUST_INDEX_AUTHORITY_CHIP} />
    </div>
  );
}

export function TrustIndexPolicyAuthorityCell({ row }: { row: TrustEnvelopeIndexRowDTO }) {
  return (
    <div className={styles.chipCell}>
      <PolicyAuthorityPill state={row.policyAuthority} {...TRUST_INDEX_POLICY_CHIP} appearance="text" />
    </div>
  );
}

function TrustIndexAuditOpenLink({
  row,
  auditHref,
  disabled,
  unavailable,
}: {
  row: TrustEnvelopeIndexRowDTO;
  auditHref: string;
  disabled?: boolean;
  unavailable?: boolean;
}) {
  const auditTitle = row.auditReference;
  const location = useLocation();
  const inRouter = useInRouterContext();

  if (disabled || unavailable) {
    const label = unavailable
      ? TRUST_ENVELOPE_INDEX_COPY.table.unavailable
      : TRUST_ENVELOPE_INDEX_COPY.table.open;
    return (
      <button
        type="button"
        className={styles.openButton}
        disabled
        data-trust-index-audit-open={row.envelopeId}
        data-trust-index-audit-unavailable={unavailable ? row.envelopeId : undefined}
        title={
          unavailable
            ? TRUST_ENVELOPE_INDEX_COPY.table.auditUnavailableReason
            : auditTitle
        }
        aria-label={
          unavailable
            ? TRUST_ENVELOPE_INDEX_COPY.table.auditUnavailableReason
            : undefined
        }
      >
        {label}
      </button>
    );
  }

  if (inRouter) {
    return (
      <Link
        to={auditHref}
        state={{ parentSearch: location.search }}
        className={[styles.openButton, shared.focusVisible].join(' ')}
        data-trust-index-audit-open={row.envelopeId}
        data-audit-reference={row.auditReference}
        title={auditTitle}
        aria-label={TRUST_ENVELOPE_INDEX_COPY.table.openAuditRecord(row.auditReference)}
      >
        {TRUST_ENVELOPE_INDEX_COPY.table.open}
      </Link>
    );
  }

  return (
    <a
      href={auditHref}
      className={[styles.openButton, shared.focusVisible].join(' ')}
      data-trust-index-audit-open={row.envelopeId}
      data-audit-reference={row.auditReference}
      title={auditTitle}
    >
      {TRUST_ENVELOPE_INDEX_COPY.table.open}
    </a>
  );
}

export function TrustIndexAuditCell({
  row,
  disabled,
}: {
  row: TrustEnvelopeIndexRowDTO;
  disabled?: boolean;
}) {
  const auditHref = buildTrustEnvelopeAuditReferenceHref(row.auditReference, row.envelopeId);
  const unavailable = row.auditRecordStatus === 'unavailable';
  return (
    <div className={styles.auditCell} data-trust-index-audit={row.envelopeId}>
      <TrustIndexAuditOpenLink
        row={row}
        auditHref={auditHref}
        disabled={disabled}
        unavailable={unavailable}
      />
    </div>
  );
}
