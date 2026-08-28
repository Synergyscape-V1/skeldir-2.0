import type { AuditArtifact } from '../../../operationalAudit/types';
import {
  auditRecordClassTooltip,
  formatAuditRecordClassLabel,
  formatForensicActionLabel,
} from '../../../operationalAudit/forensicAuditDisplay';
import styles from './AuditArtifactMetadataPanel.module.css';

export interface AuditArtifactMetadataPanelProps {
  artifact?: AuditArtifact;
}

export function AuditArtifactMetadataPanel({ artifact }: AuditArtifactMetadataPanelProps) {
  if (!artifact) return null;
  return (
    <dl className={styles.panel} data-artifact-metadata-panel>
      <div>
        <dt>Event id</dt>
        <dd>{artifact.eventId}</dd>
      </div>
      <div>
        <dt>Action</dt>
        <dd>{formatForensicActionLabel(artifact.eventType)}</dd>
      </div>
      <div>
        <dt>Actor</dt>
        <dd>{artifact.actorLabel}</dd>
      </div>
      {artifact.agentLabel ? (
        <div>
          <dt>Agent</dt>
          <dd>{artifact.agentLabel}</dd>
        </div>
      ) : null}
      <div>
        <dt>Subject</dt>
        <dd>{artifact.subjectLabel}</dd>
      </div>
      <div>
        <dt>Timestamp</dt>
        <dd>{new Date(artifact.occurredAt).toLocaleString()}</dd>
      </div>
      <div>
        <dt>Record class</dt>
        <dd data-audit-record-class={artifact.tier} title={auditRecordClassTooltip(artifact.tier)}>
          {formatAuditRecordClassLabel(artifact.tier)}
        </dd>
      </div>
      <div>
        <dt>Reconstruction status</dt>
        <dd data-reconstruction-status={artifact.reconstructionStatus ?? 'unavailable'}>
          {artifact.reconstructionStatus ?? 'unavailable'}
        </dd>
      </div>
      {artifact.previousStateHash ? (
        <div>
          <dt>Previous state hash</dt>
          <dd data-previous-state-hash>{artifact.previousStateHash}</dd>
        </div>
      ) : null}
      <div>
        <dt>Signature status</dt>
        <dd data-signature-status={artifact.signatureStatus}>{artifact.signatureStatus}</dd>
      </div>
    </dl>
  );
}
