import type { ExceptionOverviewSummary } from '../../../ledger/types';
import { EXCEPTIONS_PAGE_COPY } from '../../../exceptions/copy';
import styles from './ExceptionsSummaryRow.module.css';

export interface ExceptionsSummaryRowProps {
  summary: ExceptionOverviewSummary;
  loading?: boolean;
}

export function ExceptionsSummaryRow({ summary, loading = false }: ExceptionsSummaryRowProps) {
  const tiles = [
    { id: 'open_exceptions', label: EXCEPTIONS_PAGE_COPY.summary.openExceptions, value: summary.openExceptions },
    {
      id: 'policy_approvals_required',
      label: EXCEPTIONS_PAGE_COPY.summary.policyApprovalsRequired,
      value: summary.policyApprovalsRequired,
    },
    {
      id: 'signature_failures',
      label: EXCEPTIONS_PAGE_COPY.summary.signatureFailures,
      value: summary.signatureFailures,
    },
    {
      id: 'integration_repairs_needed',
      label: EXCEPTIONS_PAGE_COPY.summary.integrationRepairsNeeded,
      value: summary.integrationRepairsNeeded,
    },
  ] as const;

  return (
    <section
      className={styles.section}
      data-exceptions-summary-row
      aria-busy={loading ? 'true' : undefined}
      aria-label={EXCEPTIONS_PAGE_COPY.summary.ariaLabel}
    >
      <div className={styles.grid}>
        {tiles.map((tile) => (
          <article key={tile.id} className={styles.card} data-summary-metric={tile.id}>
            <div className={styles.body}>
              <span className={styles.label}>{tile.label}</span>
              <span className={styles.value} data-summary-metric-value={tile.id}>
                {tile.value}
              </span>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
