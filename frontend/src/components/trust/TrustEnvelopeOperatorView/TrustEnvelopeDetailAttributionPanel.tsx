import type { TrustEnvelopeAttributionData } from '../../../detail/types';
import { TRUST_ENVELOPE_DETAIL_COPY } from '../../../trustIndex/trustEnvelopeDetailCopy';
import panelStyles from './TrustEnvelopeDetailPanel.module.css';
import styles from './TrustEnvelopeDetailAttributionPanel.module.css';

export interface TrustEnvelopeDetailAttributionPanelProps {
  data: TrustEnvelopeAttributionData;
}

export function TrustEnvelopeDetailAttributionPanel({ data }: TrustEnvelopeDetailAttributionPanelProps) {
  const copy = TRUST_ENVELOPE_DETAIL_COPY.panels.attribution;
  const allocationLabel = copy.allocationLabel(data.allocationChannel, data.allocationPercent);

  return (
    <section
      className={panelStyles.panel}
      data-panel="attribution"
      data-trust-envelope-attribution-panel
    >
      <div className={styles.titleRow}>
        <h2 className={[panelStyles.panelTitle, styles.panelHeading].join(' ')}>{copy.title}</h2>
      </div>

      <dl className={styles.fieldGrid}>
        <div className={styles.fieldRow}>
          <dt className={styles.fieldLabel}>{copy.selectedModel}</dt>
          <dd className={styles.fieldValue} data-trust-envelope-attribution-model>
            {data.selectedModel}
          </dd>
        </div>
        <div className={styles.fieldRow}>
          <dt className={styles.fieldLabel}>{copy.modelFamily}</dt>
          <dd className={styles.fieldValue} data-trust-envelope-model-family>
            {data.modelFamily}
          </dd>
        </div>
        <div className={styles.fieldRow}>
          <dt className={styles.fieldLabel}>{copy.modelAgreementTier}</dt>
          <dd className={styles.fieldValue} data-trust-envelope-model-agreement-tier>
            {data.modelAgreementTier}
          </dd>
        </div>
        <div className={styles.fieldRow}>
          <dt className={styles.fieldLabel}>{copy.allocationResult}</dt>
          <dd className={styles.fieldValueWithChip}>
            <span data-trust-envelope-allocation-result>{allocationLabel}</span>
          </dd>
        </div>
      </dl>

      <p className={styles.boundaryNote} data-trust-envelope-attribution-boundary>
        {data.boundaryNote}
      </p>
    </section>
  );
}
