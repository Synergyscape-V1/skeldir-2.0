import { OPERATIONAL_AUDIT_COPY } from '../../../operationalAudit/copy';
import { DataUnavailablePanel } from '../../trust/DataUnavailablePanel/DataUnavailablePanel';
import { ErrorBanner } from '../../layout/ErrorBanner/ErrorBanner';
import styles from './AuditArtifactUnavailablePanel.module.css';

export interface AuditArtifactUnavailablePanelProps {
  variant: 'unavailable' | 'corrupted' | 'access_denied' | 'invalid_signature';
  reason?: string;
}

export function AuditArtifactUnavailablePanel({
  variant,
  reason,
}: AuditArtifactUnavailablePanelProps) {
  if (variant === 'access_denied') {
    return (
      <div role="alert" data-artifact-access-denied>
        <ErrorBanner variant="permission_denied" />
        <p className={styles.copy}>{OPERATIONAL_AUDIT_COPY.permissionDeniedArtifact}</p>
      </div>
    );
  }

  if (variant === 'invalid_signature') {
    return (
      <div role="alert" data-artifact-invalid-signature>
        <ErrorBanner variant="error" message={reason ?? OPERATIONAL_AUDIT_COPY.artifactInvalidSignature} />
      </div>
    );
  }

  return (
    <DataUnavailablePanel
      reason={reason ?? OPERATIONAL_AUDIT_COPY.artifactUnavailableTitle}
      whatStillWorks="Audit event metadata remains visible in the ledger."
    />
  );
}
