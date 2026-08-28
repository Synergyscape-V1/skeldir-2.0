import type { ForensicChainAssessment } from '../../../operationalAudit/forensicChainIntegrity';
import { OPERATIONAL_AUDIT_COPY } from '../../../operationalAudit/copy';
import styles from './AuditForensicChainPanel.module.css';

export interface AuditForensicChainPanelProps {
  assessment: ForensicChainAssessment;
}

export function AuditForensicChainPanel({ assessment }: AuditForensicChainPanelProps) {
  const badgeClass =
    assessment.verdict === 'intact'
      ? styles.badgeIntact
      : assessment.verdict === 'broken'
        ? styles.badgeBroken
        : styles.badgeUnavailable;

  const badgeLabel =
    assessment.verdict === 'intact'
      ? OPERATIONAL_AUDIT_COPY.chainIntactBadge
      : assessment.verdict === 'broken'
        ? OPERATIONAL_AUDIT_COPY.chainBrokenBadge
        : OPERATIONAL_AUDIT_COPY.chainUnavailableBadge;

  const badgeDetail =
    assessment.verdict === 'intact'
      ? OPERATIONAL_AUDIT_COPY.chainIntactDetail
      : assessment.verdict === 'broken'
        ? OPERATIONAL_AUDIT_COPY.chainBrokenDetail
        : assessment.detail;

  return (
    <section className={styles.panel} data-forensic-chain-panel aria-label={OPERATIONAL_AUDIT_COPY.hashChainSectionTitle}>
      <h3 className={styles.title}>{OPERATIONAL_AUDIT_COPY.hashChainSectionTitle}</h3>
      <p className={styles.readOnly}>{OPERATIONAL_AUDIT_COPY.forensicDrawerReadOnly}</p>
      <div className={[styles.badge, badgeClass].join(' ')} data-chain-verdict={assessment.verdict}>
        {badgeLabel}
      </div>
      {badgeDetail ? <p className={styles.detail}>{badgeDetail}</p> : null}
      {assessment.previousEventId ? (
        <dl className={styles.meta}>
          <div>
            <dt>Previous event</dt>
            <dd>{assessment.previousEventId}</dd>
          </div>
          {assessment.previousArtifactHash ? (
            <div>
              <dt>Prior artifact hash</dt>
              <dd data-prior-artifact-hash>{assessment.previousArtifactHash}</dd>
            </div>
          ) : null}
          {assessment.currentPreviousLinkHash ? (
            <div>
              <dt>Previous link hash</dt>
              <dd data-previous-link-hash>{assessment.currentPreviousLinkHash}</dd>
            </div>
          ) : null}
        </dl>
      ) : null}
      {assessment.detail && assessment.verdict !== 'intact' && assessment.verdict !== 'broken' ? (
        <p className={styles.detail}>{assessment.detail}</p>
      ) : null}
    </section>
  );
}
