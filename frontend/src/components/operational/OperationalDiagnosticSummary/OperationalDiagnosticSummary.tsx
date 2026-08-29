import { Card } from '../../layout/Card/Card';
import { OPERATIONAL_AUDIT_COPY } from '../../../operationalAudit/copy';
import type { DiagnosticSummary } from '../../../operationalAudit/types';
import styles from './OperationalDiagnosticSummary.module.css';

export interface OperationalDiagnosticSummaryProps {
  summary?: DiagnosticSummary;
  loading?: boolean;
}

export function OperationalDiagnosticSummary({ summary, loading }: OperationalDiagnosticSummaryProps) {
  if (loading || !summary) {
    return (
      <div className={styles.grid} aria-busy="true" data-diagnostic-summary>
        {[1, 2, 3, 4].map((key) => (
          <Card key={key} className={styles.card}>
            <div className={styles.skeleton} />
          </Card>
        ))}
      </div>
    );
  }

  const cards = [
    { label: OPERATIONAL_AUDIT_COPY.summaryTaskFailures, value: summary.taskFailures },
    { label: OPERATIONAL_AUDIT_COPY.summaryIntegrationIssues, value: summary.integrationIssues },
    { label: OPERATIONAL_AUDIT_COPY.summaryConfidenceDelayed, value: summary.confidenceDelayed },
    {
      label: OPERATIONAL_AUDIT_COPY.summaryTrustApiPaused,
      value: summary.trustApiPaused ? 'Yes' : 'No',
    },
  ];

  return (
    <div className={styles.grid} data-diagnostic-summary>
      {cards.map((card) => (
        <Card key={card.label} className={styles.card}>
          <h3 className={styles.label}>{card.label}</h3>
          <p className={styles.value}>{card.value}</p>
        </Card>
      ))}
    </div>
  );
}
