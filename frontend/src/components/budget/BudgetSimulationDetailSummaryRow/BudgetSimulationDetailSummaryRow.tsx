import type { BudgetSimulationDetailDTO } from '../../../detail/types';
import { BUDGET_DETAIL_COPY } from '../../../budget/copy';
import { formatBpsAsPercentOneDecimal, formatMoneyMinorDisplay } from '../../../lib/money';
import { COMMAND_CENTER_CHIP_PROPS, COMMAND_CENTER_POLICY_CHIP_PROPS } from '../../../commandCenter/commandCenterChipProps';
import { AuthorityBadge } from '../../trust/AuthorityBadge/AuthorityBadge';
import { PolicyAuthorityPill } from '../../trust/PolicyAuthorityPill/PolicyAuthorityPill';
import { IconArrowUpRight } from '../../icons/StatusIcons';
import shared from '../../../styles/shared.module.css';
import styles from './BudgetSimulationDetailSummaryRow.module.css';

function channelLabel(channel: string): string {
  return channel
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function AnchorDrillDown({
  href,
  label,
  metricId,
}: {
  href: string;
  label: string;
  metricId: string;
}) {
  return (
    <div className={styles.actionFooter}>
      <a
        href={href}
        className={[styles.drillDown, shared.focusVisible].join(' ')}
        data-summary-drilldown={metricId}
      >
        <span>{label}</span>
        <IconArrowUpRight className={styles.drillDownChevron} />
      </a>
    </div>
  );
}

export interface BudgetSimulationDetailSummaryRowProps {
  detail: BudgetSimulationDetailDTO;
}

export function BudgetSimulationDetailSummaryRow({ detail }: BudgetSimulationDetailSummaryRowProps) {
  const topAllocation = [...detail.projectedAllocation].sort((a, b) => b.shareBps - a.shareBps)[0];
  const confidenceUnavailable = detail.confidence.status === 'unavailable';
  const statusLabel =
    BUDGET_DETAIL_COPY.status[detail.simulationStatus] ?? detail.simulationStatus;

  return (
    <section
      className={styles.section}
      data-budget-detail-summary-row
      aria-label={BUDGET_DETAIL_COPY.summary.ariaLabel}
    >
      <div className={styles.grid}>
        <article className={styles.card} data-summary-metric="verified_revenue_basis">
          <div className={styles.body}>
            <div className={styles.topRow}>
              <span className={styles.label}>{BUDGET_DETAIL_COPY.summary.verifiedRevenue}</span>
              <span className={styles.chip}>
                <AuthorityBadge authority="deterministic" {...COMMAND_CENTER_CHIP_PROPS} />
              </span>
            </div>
            <span className={styles.value} data-summary-metric-value="verified_revenue_basis">
              {formatMoneyMinorDisplay(detail.verifiedRevenueBasisMinor, detail.currencyCode)}
            </span>
            <span className={styles.meta}>Deterministic commerce evidence</span>
          </div>
          <AnchorDrillDown
            href="#budget-detail-assumptions"
            label={BUDGET_DETAIL_COPY.sections.assumptions}
            metricId="verified_revenue_basis"
          />
        </article>

        <article
          className={styles.card}
          data-summary-metric="policy_authority"
          data-budget-policy-authority-section
          id="budget-detail-policy"
        >
          <div className={styles.body}>
            <div className={styles.topRow}>
              <span className={styles.label}>{BUDGET_DETAIL_COPY.summary.policyAuthority}</span>
              <span className={styles.chip}>
                <PolicyAuthorityPill state={detail.policyAuthority} {...COMMAND_CENTER_POLICY_CHIP_PROPS} />
              </span>
            </div>
            <span className={styles.value} data-summary-metric-value="policy_authority">
              {detail.policyAuthority.replace(/_/g, ' ')}
            </span>
            <span className={styles.meta}>Submission remains policy-gated</span>
          </div>
          <AnchorDrillDown
            href="#budget-detail-policy-detail"
            label={BUDGET_DETAIL_COPY.summary.reviewPolicy}
            metricId="policy_authority"
          />
        </article>

        <article className={styles.card} data-summary-metric="confidence" id="budget-detail-confidence">
          <div className={styles.body}>
            <div className={styles.topRow}>
              <span className={styles.label}>{BUDGET_DETAIL_COPY.summary.confidence}</span>
              <span className={styles.chip}>
                <AuthorityBadge
                  authority={confidenceUnavailable ? 'unavailable' : 'probabilistic'}
                  {...COMMAND_CENTER_CHIP_PROPS}
                />
              </span>
            </div>
            <span
              className={[styles.value, confidenceUnavailable ? styles.valueWarning : ''].filter(Boolean).join(' ')}
              data-summary-metric-value="confidence"
            >
              {confidenceUnavailable
                ? BUDGET_DETAIL_COPY.summary.unavailable
                : BUDGET_DETAIL_COPY.summary.available}
            </span>
            {confidenceUnavailable && detail.confidence.reason ? (
              <span className={[styles.meta, styles.metaWarning].join(' ')}>{detail.confidence.reason}</span>
            ) : (
              <span className={styles.meta}>Artifact-backed interval when diagnostically available</span>
            )}
          </div>
          <AnchorDrillDown
            href="#budget-detail-confidence-detail"
            label={BUDGET_DETAIL_COPY.summary.reviewConfidence}
            metricId="confidence"
          />
        </article>

        <article className={styles.card} data-summary-metric="simulation_status">
          <div className={styles.body}>
            <div className={styles.topRow}>
              <span className={styles.label}>{BUDGET_DETAIL_COPY.summary.status}</span>
              <span className={styles.chip}>
                <AuthorityBadge authority="deterministic" {...COMMAND_CENTER_CHIP_PROPS} />
              </span>
            </div>
            <span
              className={styles.value}
              data-summary-metric-value="simulation_status"
              data-simulation-status={detail.simulationStatus}
            >
              {statusLabel}
            </span>
            {topAllocation ? (
              <span className={styles.meta}>
                {BUDGET_DETAIL_COPY.summary.topAllocation}: {channelLabel(topAllocation.channel)}{' '}
                ({formatBpsAsPercentOneDecimal(topAllocation.shareBps)})
              </span>
            ) : null}
          </div>
          <AnchorDrillDown
            href="#budget-detail-allocation"
            label={BUDGET_DETAIL_COPY.summary.reviewAllocation}
            metricId="simulation_status"
          />
        </article>
      </div>
    </section>
  );
}
