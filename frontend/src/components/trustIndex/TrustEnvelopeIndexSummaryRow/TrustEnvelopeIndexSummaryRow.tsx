import { Link } from 'react-router-dom';

import type { TrustEnvelopeIndexSummary } from '../../../ledger/types';
import type { TrustIndexFilters } from '../../../trustIndex/trustIndexClient';
import { formatMoneyMinorDisplay } from '../../../lib/money';
import { TRUST_ENVELOPE_INDEX_COPY } from '../../../trustIndex/copy';
import {
  buildClearConfidenceAvailabilityHref,
  buildUnavailableConfidenceIsolateHref,
} from '../../../trustIndex/trustIndexQueryState';
import {
  resolveUnavailableConfidenceDisposition,
  unavailableConfidenceMetaCopy,
  unavailableConfidenceMetaTone,
  unavailableConfidenceValueTone,
} from '../../../trustIndex/unavailableConfidenceSummaryPresentation';
import { COMMAND_CENTER_CHIP_PROPS } from '../../../commandCenter/commandCenterChipProps';
import { AuthorityBadge } from '../../trust/AuthorityBadge/AuthorityBadge';
import { IconArrowUpRight } from '../../icons/StatusIcons';
import shared from '../../../styles/shared.module.css';
import styles from './TrustEnvelopeIndexSummaryRow.module.css';

export interface TrustEnvelopeIndexSummaryRowProps {
  summary: TrustEnvelopeIndexSummary;
  filters: TrustIndexFilters;
  loading?: boolean;
}

export function TrustEnvelopeIndexSummaryRow({
  summary,
  filters,
  loading = false,
}: TrustEnvelopeIndexSummaryRowProps) {
  const revenueDisplay = formatMoneyMinorDisplay(summary.verifiedRevenueMinor, summary.currencyCode);
  const unavailableCount = summary.unavailableConfidenceCount;
  const disposition = resolveUnavailableConfidenceDisposition(
    unavailableCount,
    summary.unavailableConfidenceCauses,
  );
  const meta = unavailableConfidenceMetaCopy(disposition, summary.unavailableConfidenceCauses);
  const valueTone = unavailableConfidenceValueTone(disposition);
  const metaTone = unavailableConfidenceMetaTone(disposition);
  const alreadyIsolated = filters.confidenceAvailability === 'unavailable';
  const isolateHref = buildUnavailableConfidenceIsolateHref(filters);
  const clearHref = buildClearConfidenceAvailabilityHref(filters);

  return (
    <section
      className={styles.section}
      data-trust-index-summary-row
      aria-busy={loading ? 'true' : undefined}
      aria-label="TrustEnvelope index summary"
    >
      <div className={styles.grid}>
        <article className={styles.card} data-summary-metric="total_count">
          <div className={styles.body}>
            <div className={styles.topRow}>
              <span className={styles.label}>{TRUST_ENVELOPE_INDEX_COPY.summary.totalTrustEnvelopes}</span>
            </div>
            <span className={styles.value} data-summary-metric-value="total_count">
              {summary.totalCount}
            </span>
            <span className={styles.meta}>{TRUST_ENVELOPE_INDEX_COPY.summary.addedLast24h(summary.addedLast24h)}</span>
          </div>
        </article>

        <article className={styles.card} data-summary-metric="verified_revenue">
          <div className={styles.body}>
            <div className={styles.topRow}>
              <span className={styles.label}>{TRUST_ENVELOPE_INDEX_COPY.summary.deterministicVerifiedRevenue}</span>
              <span className={styles.chip}>
                <AuthorityBadge authority="deterministic" {...COMMAND_CENTER_CHIP_PROPS} />
              </span>
            </div>
            <span className={styles.value} data-summary-metric-value="verified_revenue">
              {revenueDisplay}
            </span>
          </div>
        </article>

        <article className={styles.card} data-summary-metric="audit_linked">
          <div className={styles.body}>
            <div className={styles.topRow}>
              <span className={styles.label}>{TRUST_ENVELOPE_INDEX_COPY.summary.auditLinked}</span>
            </div>
            <span className={styles.value} data-summary-metric-value="audit_linked">
              {summary.auditLinkedCount} / {summary.totalCount}
            </span>
            <span className={styles.meta}>
              {TRUST_ENVELOPE_INDEX_COPY.summary.auditPendingReview(summary.auditPendingReviewCount)}
            </span>
          </div>
        </article>

        <article
          className={styles.card}
          data-summary-metric="unavailable_confidence"
          data-unavailable-confidence-disposition={disposition}
        >
          <div className={styles.body}>
            <div className={styles.topRow}>
              <span className={styles.label}>{TRUST_ENVELOPE_INDEX_COPY.summary.unavailableConfidence}</span>
              <span className={styles.chip}>
                <AuthorityBadge authority="unavailable" {...COMMAND_CENTER_CHIP_PROPS} />
              </span>
            </div>
            <span
              className={valueTone === 'warning' ? styles.valueWarning : styles.value}
              data-summary-metric-value="unavailable_confidence"
              data-unavailable-confidence-count={unavailableCount}
              data-unavailable-confidence-value-mode={alreadyIsolated ? 'count' : 'ratio'}
            >
              {alreadyIsolated
                ? TRUST_ENVELOPE_INDEX_COPY.summary.unavailableConfidenceCountOnly(unavailableCount)
                : TRUST_ENVELOPE_INDEX_COPY.summary.unavailableConfidenceRatio(
                    unavailableCount,
                    summary.totalCount,
                  )}
            </span>
            <span
              className={[
                styles.meta,
                metaTone === 'success'
                  ? styles.metaSuccess
                  : metaTone === 'warning'
                    ? styles.metaWarning
                    : '',
                styles.metaSingleLine,
              ]
                .filter(Boolean)
                .join(' ')}
              data-unavailable-confidence-meta
              title={TRUST_ENVELOPE_INDEX_COPY.summary.unavailableConfidenceBoundaryTitle}
            >
              {meta}
            </span>          </div>
          {unavailableCount > 0 ? (
            <div className={styles.actionFooter}>
              {alreadyIsolated ? (
                <Link
                  to={clearHref}
                  className={[styles.drillDown, shared.focusVisible].join(' ')}
                  data-summary-drilldown="unavailable_confidence"
                  data-unavailable-confidence-cta="clear"
                >
                  <span>{TRUST_ENVELOPE_INDEX_COPY.summary.clearUnavailableConfidenceFilter}</span>
                  <IconArrowUpRight className={styles.drillDownChevron} />
                </Link>
              ) : (
                <Link
                  to={isolateHref}
                  className={[styles.drillDown, shared.focusVisible].join(' ')}
                  data-summary-drilldown="unavailable_confidence"
                  data-unavailable-confidence-cta="isolate"
                >
                  <span>{TRUST_ENVELOPE_INDEX_COPY.summary.viewUnavailableConfidence}</span>
                  <IconArrowUpRight className={styles.drillDownChevron} />
                </Link>
              )}
            </div>
          ) : null}
        </article>
      </div>
    </section>
  );
}
