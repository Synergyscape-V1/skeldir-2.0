import { OPERATIONAL_AUDIT_COPY } from '../../../operationalAudit/copy';
import type { AuditArtifact } from '../../../operationalAudit/types';
import styles from './AuditTechnicalDetailsSections.module.css';

export interface AuditTechnicalDetailsSectionsProps {
  artifact?: AuditArtifact;
}

export function AuditTechnicalDetailsSections({ artifact }: AuditTechnicalDetailsSectionsProps) {
  if (!artifact) return null;

  return (
    <>
      {artifact.idempotencyKey ? (
        <section className={styles.section} data-forensic-idempotency-section>
          <h3 className={styles.title}>{OPERATIONAL_AUDIT_COPY.forensicIdempotencyTitle}</h3>
          <p className={styles.body}>{OPERATIONAL_AUDIT_COPY.forensicIdempotencyBody}</p>
          <code className={styles.mono} data-idempotency-key>
            {artifact.idempotencyKey}
          </code>
        </section>
      ) : null}
    </>
  );
}
