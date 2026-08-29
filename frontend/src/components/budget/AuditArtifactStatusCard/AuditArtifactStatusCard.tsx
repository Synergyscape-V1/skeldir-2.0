import { BUDGET_SIMULATION_COPY } from '../../../budget/copy';
import type { AuditArtifactStatus } from '../../../budget/budgetSimulationTypes';
import { AuditReferenceLink } from '../../audit/AuditReferenceLink/AuditReferenceLink';
import { IconSuccess } from '../../icons/StatusIcons';
import shared from '../../../styles/shared.module.css';
import styles from './AuditArtifactStatusCard.module.css';

export interface AuditArtifactStatusCardProps {
  status: AuditArtifactStatus;
  auditReference: string;
}

function statusLabel(status: AuditArtifactStatus): string {
  if (status === 'written') return BUDGET_SIMULATION_COPY.auditArtifact.written;
  if (status === 'pending') return BUDGET_SIMULATION_COPY.auditArtifact.pending;
  return BUDGET_SIMULATION_COPY.auditArtifact.unavailable;
}

function statusCaption(status: AuditArtifactStatus): string {
  if (status === 'written') return BUDGET_SIMULATION_COPY.auditArtifact.readyCaption;
  return BUDGET_SIMULATION_COPY.auditArtifact.pendingCaption;
}

export function AuditArtifactStatusCard({ status, auditReference }: AuditArtifactStatusCardProps) {
  return (
    <section
      className={styles.panel}
      aria-label={BUDGET_SIMULATION_COPY.auditArtifact.title}
      data-audit-artifact-status-card
      data-budget-elevated-panel="true"
    >
      <div className={styles.headerRow}>
        <h3 className={styles.title}>{BUDGET_SIMULATION_COPY.auditArtifact.title}</h3>
        <span className={styles.statusTag} data-audit-status={status}>
          <span className={shared.iconWithLabel}>
            {status === 'written' ? <IconSuccess aria-hidden="true" /> : null}
            <span>{statusLabel(status)}</span>
          </span>
        </span>
      </div>
      <div className={styles.hashRow}>
        <span className={styles.hashLabel}>{BUDGET_SIMULATION_COPY.auditArtifact.referenceLabel}</span>
        <AuditReferenceLink auditReference={auditReference} />
      </div>
      <p className={styles.caption}>{statusCaption(status)}</p>
    </section>
  );
}
