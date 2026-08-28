import type { AuditArtifact } from '../../../operationalAudit/types';
import { AuditReferenceLink } from '../../audit/AuditReferenceLink/AuditReferenceLink';
import styles from './AuditArtifactHashPanel.module.css';

export interface AuditArtifactHashPanelProps {
  artifact?: AuditArtifact;
}

export function AuditArtifactHashPanel({ artifact }: AuditArtifactHashPanelProps) {
  if (!artifact?.eventId) return null;

  return (
    <div className={styles.panel} data-artifact-audit-reference-panel>
      <p className={styles.label}>Audit reference</p>
      <AuditReferenceLink auditReference={artifact.eventId} />
    </div>
  );
}
