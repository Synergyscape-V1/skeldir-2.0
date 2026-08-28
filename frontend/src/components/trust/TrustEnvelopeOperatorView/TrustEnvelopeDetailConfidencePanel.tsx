import type { TrustEnvelopeBenchmarkData, TrustEnvelopeConfidenceData } from '../../../detail/types';
import {
  formatTrustEnvelopeCredibleIntervalDisplay,
  formatTrustEnvelopeModelFreshnessDisplay,
  formatTrustEnvelopePosteriorSupportDisplay,
} from '../../../trustIndex/trustEnvelopeDetailDisplay';
import { TRUST_ENVELOPE_DETAIL_COPY } from '../../../trustIndex/trustEnvelopeDetailCopy';
import { TRUST_ENVELOPE_DETAIL_CHIP_PROPS } from '../../../trustIndex/trustEnvelopeDetailChipProps';
import { AuthorityBadge } from '../AuthorityBadge/AuthorityBadge';
import { DataUnavailablePanel } from '../DataUnavailablePanel/DataUnavailablePanel';
import { CollapsibleSection } from '../../layout/CollapsibleSection/CollapsibleSection';
import { TrustEnvelopeDetailBenchmarkPanel } from './TrustEnvelopeDetailBenchmarkPanel';
import shared from '../../../styles/shared.module.css';
import panelStyles from './TrustEnvelopeDetailPanel.module.css';
import styles from './TrustEnvelopeDetailConfidencePanel.module.css';

export interface TrustEnvelopeDetailConfidencePanelProps {
  data: TrustEnvelopeConfidenceData;
  benchmark?: TrustEnvelopeBenchmarkData;
  referenceAt: string;
}

function validateConfidenceIntegrity(data: TrustEnvelopeConfidenceData): string | null {
  if (data.status !== 'available') return null;
  if (data.intervalLower === undefined || data.intervalUpper === undefined) {
    return 'Confidence interval is required when status is available.';
  }
  if (data.posteriorSupport === undefined) {
    return 'Posterior support is required when status is available.';
  }
  if (!data.modelFreshnessAt?.trim()) {
    return 'Model freshness timestamp is required when status is available.';
  }
  if (!data.boundaryNote.trim()) {
    return 'boundaryNote is required';
  }
  return null;
}

export function TrustEnvelopeDetailConfidencePanel({
  data,
  benchmark,
  referenceAt,
}: TrustEnvelopeDetailConfidencePanelProps) {
  const copy = TRUST_ENVELOPE_DETAIL_COPY.panels.confidence;
  const benchmarkCopy = TRUST_ENVELOPE_DETAIL_COPY.panels.benchmark;
  const integrityError = validateConfidenceIntegrity(data);

  const benchmarkFold =
    benchmark ? (
      <CollapsibleSection summary={benchmarkCopy.title} dataAttribute="trust-envelope-benchmark-fold">
        <TrustEnvelopeDetailBenchmarkPanel data={benchmark} embedded />
      </CollapsibleSection>
    ) : null;

  if (integrityError) {
    return (
      <section className={panelStyles.panel} data-panel="confidence" role="alert">
        <div className={shared.errorState}>{integrityError}</div>
      </section>
    );
  }

  if (data.status === 'unavailable') {
    return (
      <section
        className={panelStyles.panel}
        data-panel="confidence"
        data-trust-envelope-confidence-panel
        data-trust-envelope-confidence-state="unavailable"
      >
        <div className={styles.titleRow}>
          <h2 className={[panelStyles.panelTitle, styles.panelHeading].join(' ')}>{copy.title}</h2>
        </div>
        <DataUnavailablePanel
          variant="no_confidence"
          reason={
            data.reason ?? 'Confidence is unavailable. Deterministic verification remains active.'
          }
        />
        <p className={styles.boundaryNote} data-trust-envelope-confidence-boundary>
          {data.boundaryNote}
        </p>
        {benchmarkFold}
      </section>
    );
  }

  if (data.status === 'delayed') {
    return (
      <section
        className={panelStyles.panel}
        data-panel="confidence"
        data-trust-envelope-confidence-panel
        data-trust-envelope-confidence-state="delayed"
        role="status"
      >
        <div className={styles.titleRow}>
          <h2 className={[panelStyles.panelTitle, styles.panelHeading].join(' ')}>{copy.title}</h2>
        </div>
        <p className={styles.delayedStatus} data-trust-envelope-confidence-delayed>
          {copy.delayedStatus}
          {data.reason ? ` — ${data.reason}` : null}
        </p>
        <p className={styles.boundaryNote} data-trust-envelope-confidence-boundary>
          {data.boundaryNote}
        </p>
        {benchmarkFold}
      </section>
    );
  }

  const intervalDisplay = formatTrustEnvelopeCredibleIntervalDisplay(
    data.intervalLower!,
    data.intervalUpper!,
  );
  const posteriorDisplay = formatTrustEnvelopePosteriorSupportDisplay(data.posteriorSupport!);
  const freshnessDisplay = formatTrustEnvelopeModelFreshnessDisplay(
    data.modelFreshnessAt!,
    referenceAt,
  );

  return (
    <section
      className={panelStyles.panel}
      data-panel="confidence"
      data-trust-envelope-confidence-panel
      data-trust-envelope-confidence-state="available"
    >
      <div className={styles.titleRow}>
        <h2 className={[panelStyles.panelTitle, styles.panelHeading].join(' ')}>{copy.title}</h2>
      </div>

      <dl className={styles.fieldGrid}>
        <div className={styles.fieldRow}>
          <dt className={styles.fieldLabel}>{copy.credibleInterval95}</dt>
          <dd className={styles.fieldValueWithChip}>
            <span data-trust-envelope-credible-interval>{intervalDisplay}</span>
            <span data-trust-envelope-confidence-authority="credible-interval">
              <AuthorityBadge authority="probabilistic" {...TRUST_ENVELOPE_DETAIL_CHIP_PROPS} />
            </span>
          </dd>
        </div>
        <div className={styles.fieldRow}>
          <dt className={styles.fieldLabel}>{copy.posteriorSupport}</dt>
          <dd className={styles.fieldValueWithChip}>
            <span data-trust-envelope-posterior-support>{posteriorDisplay}</span>
            <span data-trust-envelope-confidence-authority="posterior-support">
              <AuthorityBadge authority="probabilistic" {...TRUST_ENVELOPE_DETAIL_CHIP_PROPS} />
            </span>
          </dd>
        </div>
        <div className={styles.fieldRow}>
          <dt className={styles.fieldLabel}>{copy.modelFreshness}</dt>
          <dd className={styles.fieldValue} data-trust-envelope-model-freshness>
            {freshnessDisplay}
          </dd>
        </div>
      </dl>

      <p className={styles.boundaryNote} data-trust-envelope-confidence-boundary>
        {data.boundaryNote}
      </p>
      {benchmarkFold}
    </section>
  );
}
