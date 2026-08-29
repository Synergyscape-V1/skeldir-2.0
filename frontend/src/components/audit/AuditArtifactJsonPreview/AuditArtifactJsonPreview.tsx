import { OPERATIONAL_AUDIT_COPY } from '../../../operationalAudit/copy';
import styles from './AuditArtifactJsonPreview.module.css';

export interface AuditArtifactJsonPreviewProps {
  jsonPreview?: string;
  title?: string;
}

export function AuditArtifactJsonPreview({ jsonPreview, title }: AuditArtifactJsonPreviewProps) {
  if (!jsonPreview) {
    return (
      <p className={styles.hidden} data-json-preview-hidden>
        {OPERATIONAL_AUDIT_COPY.jsonPreviewHidden}
      </p>
    );
  }

  return (
    <section className={styles.section} data-artifact-json-preview>
      <h3 className={styles.label}>{title ?? OPERATIONAL_AUDIT_COPY.jsonPreviewLabel}</h3>
      <pre className={styles.pre}>
        <code>{jsonPreview}</code>
      </pre>
    </section>
  );
}
