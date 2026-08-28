import { AuditReferenceLink } from '../../audit/AuditReferenceLink/AuditReferenceLink';
import { TRUST_ENVELOPE_DETAIL_COPY } from '../../../trustIndex/trustEnvelopeDetailCopy';
import panelStyles from './TrustEnvelopeDetailPanel.module.css';
import styles from './TrustEnvelopeDetailAuditPanel.module.css';

export interface TrustEnvelopeDetailAuditPanelProps {
  auditReference: string;
  envelopeId: string;
}

export function TrustEnvelopeDetailAuditPanel({
  auditReference,
  envelopeId,
}: TrustEnvelopeDetailAuditPanelProps) {
  const copy = TRUST_ENVELOPE_DETAIL_COPY.panels.audit;

  if (!auditReference.trim()) {
    return (
      <section className={panelStyles.panel} data-panel="audit" role="alert">
        <p className={styles.error}>Audit reference is required.</p>
      </section>
    );
  }

  return (
    <section
      className={panelStyles.panel}
      data-panel="audit"
      data-trust-envelope-audit-panel
    >
      <h2 className={[panelStyles.panelTitle, styles.panelHeading].join(' ')}>{copy.title}</h2>
      <p className={styles.guidance}>{copy.guidance}</p>
      <dl className={styles.fieldGrid}>
        <div className={styles.fieldCell}>
          <dt className={styles.fieldLabel}>{copy.auditReference}</dt>
          <dd data-trust-envelope-audit-reference>
            <AuditReferenceLink auditReference={auditReference} envelopeId={envelopeId} />
          </dd>
        </div>
      </dl>
    </section>
  );
}
