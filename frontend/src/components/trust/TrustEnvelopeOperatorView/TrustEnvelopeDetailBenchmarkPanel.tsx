import type { TrustEnvelopeBenchmarkData } from '../../../detail/types';
import { TRUST_ENVELOPE_DETAIL_COPY } from '../../../trustIndex/trustEnvelopeDetailCopy';
import { DataUnavailablePanel } from '../DataUnavailablePanel/DataUnavailablePanel';
import shared from '../../../styles/shared.module.css';
import panelStyles from './TrustEnvelopeDetailPanel.module.css';
import styles from './TrustEnvelopeDetailBenchmarkPanel.module.css';

export interface TrustEnvelopeDetailBenchmarkPanelProps {
  data: TrustEnvelopeBenchmarkData;
  embedded?: boolean;
}

function validateBenchmarkIntegrity(data: TrustEnvelopeBenchmarkData): string | null {
  if (data.status !== 'available') return null;
  if (!data.rawBenchmark.trim() || !data.decisionSafeBenchmark.trim()) {
    return 'Benchmark values are required when status is available.';
  }
  if (!data.sourceClass.trim() || !data.coverageClass.trim()) {
    return 'Benchmark source and coverage class are required when status is available.';
  }
  if (!data.actionability.trim()) {
    return 'Actionability is required when status is available.';
  }
  if (data.suppressionReason !== null && !data.suppressionReason.trim()) {
    return 'Suppression reason must be null or a non-empty string.';
  }
  return null;
}

function formatComparableToPrevious(
  comparableToPrevious: boolean,
  copy: typeof TRUST_ENVELOPE_DETAIL_COPY.panels.benchmark,
): string {
  return comparableToPrevious ? copy.comparableYes : copy.comparableNo;
}

export function TrustEnvelopeDetailBenchmarkPanel({
  data,
  embedded = false,
}: TrustEnvelopeDetailBenchmarkPanelProps) {
  const copy = TRUST_ENVELOPE_DETAIL_COPY.panels.benchmark;
  const integrityError = validateBenchmarkIntegrity(data);

  if (integrityError) {
    return (
      <section className={panelStyles.panel} data-panel="benchmark" role="alert">
        <div className={shared.errorState}>{integrityError}</div>
      </section>
    );
  }

  if (data.status === 'unavailable') {
    return (
      <section
        className={panelStyles.panel}
        data-panel="benchmark"
        data-trust-envelope-benchmark-panel
        data-trust-envelope-benchmark-state="unavailable"
      >
        <div className={styles.titleRow}>
          {!embedded ? (
            <h2 className={[panelStyles.panelTitle, styles.panelHeading].join(' ')}>{copy.title}</h2>
          ) : null}
        </div>
        <DataUnavailablePanel
          variant="no_benchmark"
          reason={
            data.reason ?? 'Benchmark is unavailable. Deterministic verification remains active.'
          }
        />
      </section>
    );
  }

  if (data.status === 'suppressed') {
    return (
      <section
        className={panelStyles.panel}
        data-panel="benchmark"
        data-trust-envelope-benchmark-panel
        data-trust-envelope-benchmark-state="suppressed"
      >
        <div className={styles.titleRow}>
          {!embedded ? (
            <h2 className={[panelStyles.panelTitle, styles.panelHeading].join(' ')}>{copy.title}</h2>
          ) : null}
        </div>
        <DataUnavailablePanel
          variant="no_benchmark"
          reason={
            data.suppressionReason ??
            data.reason ??
            'Benchmark is suppressed for this envelope.'
          }
        />
      </section>
    );
  }

  return (
    <section
      className={panelStyles.panel}
      data-panel="benchmark"
      data-trust-envelope-benchmark-panel
      data-trust-envelope-benchmark-state="available"
    >
      <div className={styles.titleRow}>
        {!embedded ? (
          <h2 className={[panelStyles.panelTitle, styles.panelHeading].join(' ')}>{copy.title}</h2>
        ) : null}
      </div>

      <dl className={styles.fieldGrid}>
        <div className={styles.fieldCell}>
          <dt className={styles.fieldLabel}>{copy.rawBenchmark}</dt>
          <dd className={styles.fieldValueWithChip}>
            <span data-trust-envelope-raw-benchmark>{data.rawBenchmark}</span>
          </dd>
        </div>
        <div className={styles.fieldCell}>
          <dt className={styles.fieldLabel}>{copy.coverageClass}</dt>
          <dd className={styles.fieldValue} data-trust-envelope-coverage-class>
            {data.coverageClass}
          </dd>
        </div>
        <div className={styles.fieldCell}>
          <dt className={styles.fieldLabel}>{copy.decisionSafeBenchmark}</dt>
          <dd className={styles.fieldValueWithChip}>
            <span data-trust-envelope-decision-safe-benchmark>{data.decisionSafeBenchmark}</span>
          </dd>
        </div>
        <div className={styles.fieldCell}>
          <dt className={styles.fieldLabel}>{copy.suppressionReason}</dt>
          <dd
            className={[
              styles.fieldValue,
              data.suppressionReason === null ? styles.fieldValueMono : '',
            ]
              .filter(Boolean)
              .join(' ')}
            data-trust-envelope-suppression-reason
          >
            {data.suppressionReason ?? copy.nullLiteral}
          </dd>
        </div>
        <div className={styles.fieldCell}>
          <dt className={styles.fieldLabel}>{copy.sourceClass}</dt>
          <dd className={styles.fieldValue} data-trust-envelope-source-class>
            {data.sourceClass}
          </dd>
        </div>
        <div className={styles.fieldCell}>
          <dt className={styles.fieldLabel}>{copy.comparableToPrevious}</dt>
          <dd className={styles.fieldValue} data-trust-envelope-comparable-to-previous>
            {formatComparableToPrevious(data.comparableToPrevious, copy)}
          </dd>
        </div>
        <div className={styles.fieldCell} aria-hidden />
        <div className={styles.fieldCell}>
          <dt className={styles.fieldLabel}>{copy.actionability}</dt>
          <dd className={styles.fieldValue} data-trust-envelope-actionability>
            {data.actionability}
          </dd>
        </div>
      </dl>
    </section>
  );
}
