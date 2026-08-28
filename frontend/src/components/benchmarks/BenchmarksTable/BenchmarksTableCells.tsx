import type { BenchmarkRowDTO } from '../../../ledger/types';
import { BENCHMARKS_COPY } from '../../../benchmarks/copy';
import { formatBenchmarkValue } from '../../../benchmarks/benchmarkDisplay';
import {
  coverageRollupTooltip,
  decisionSafeAdjustmentTooltip,
  hasEstimatorTransition,
  hasVisibleSuppressionReason,
  isBenchmarkValueUnavailable,
  resolveTableActionability,
  suppressionReasonTooltip,
  unavailableBenchmarkTooltip,
} from '../../../benchmarks/benchmarkTableDisplay';
import { SUPERVISORY_TABLE_STATUS_TEXT } from '../../../commandCenter/commandCenterChipProps';
import { IconCheckmark } from '../../icons/StatusIcons';
import {
  ActionabilityPill,
  ComparabilityIndicator,
  CoverageClassBadge,
  EvidenceClassBadge,
} from '../BenchmarkBadges/BenchmarkBadges';
import styles from './BenchmarksTableCells.module.css';

export function BenchmarkNameCell({ row }: { row: BenchmarkRowDTO }) {
  return (
    <span className={styles.name} data-benchmark-name={row.benchmarkId} title={row.benchmarkName}>
      {row.benchmarkName}
    </span>
  );
}

function BenchmarkUnavailableValue({ row }: { row: BenchmarkRowDTO }) {
  const tooltip = unavailableBenchmarkTooltip();
  return (
    <span className={styles.unavailableValue} data-benchmark-unavailable={row.benchmarkId}>
      <span
        className={styles.naValue}
        data-benchmark-na-value
        title={tooltip}
        aria-label={`${BENCHMARKS_COPY.table.notAvailable}. ${tooltip}`}
      >
        {BENCHMARKS_COPY.table.notAvailable}
      </span>
    </span>
  );
}

export function BenchmarkRawValueCell({ row }: { row: BenchmarkRowDTO }) {
  if (isBenchmarkValueUnavailable(row)) {
    return <BenchmarkUnavailableValue row={row} />;
  }
  return (
    <span className={styles.value} data-benchmark-raw-value={row.benchmarkId}>
      {formatBenchmarkValue(row.rawBenchmark)}
    </span>
  );
}

export function BenchmarkDecisionSafeValueCell({ row }: { row: BenchmarkRowDTO }) {
  if (isBenchmarkValueUnavailable(row)) {
    return <BenchmarkUnavailableValue row={row} />;
  }

  const tooltip = decisionSafeAdjustmentTooltip(row);

  return (
    <span
      className={styles.valueStrong}
      data-benchmark-decision-safe-value={row.benchmarkId}
      title={tooltip}
    >
      {formatBenchmarkValue(row.decisionSafeBenchmark ?? row.rawBenchmark)}
    </span>
  );
}

export function BenchmarkEvidenceCell({ row }: { row: BenchmarkRowDTO }) {
  return (
    <div className={styles.metaCell}>
      <EvidenceClassBadge
        value={row.evidenceClass}
        showHistoricalDisclaimer
        {...SUPERVISORY_TABLE_STATUS_TEXT}
      />
    </div>
  );
}

export function BenchmarkCoverageCell({ row }: { row: BenchmarkRowDTO }) {
  const rollupTooltip = coverageRollupTooltip(row);
  return (
    <div className={styles.metaCell}>
      <CoverageClassBadge
        value={row.coverageClass}
        title={rollupTooltip}
        {...SUPERVISORY_TABLE_STATUS_TEXT}
      />
    </div>
  );
}

export function BenchmarkSuppressionCell({ row }: { row: BenchmarkRowDTO }) {
  if (!hasVisibleSuppressionReason(row)) {
    return (
      <span
        className={styles.checkmark}
        data-benchmark-suppression-clear={row.benchmarkId}
        aria-label="No suppression"
        title="No suppression"
      >
        <IconCheckmark size={16} aria-hidden />
      </span>
    );
  }

  const code = row.suppressionReasonCode ?? row.suppressionReason;
  const tooltip = suppressionReasonTooltip(row.suppressionReasonCode, row.suppressionReason);

  return (
    <span
      className={styles.reason}
      title={tooltip}
      data-benchmark-suppression={row.benchmarkId}
      data-benchmark-suppression-code={code}
    >
      {code}
    </span>
  );
}

export function BenchmarkComparabilityCell({ row }: { row: BenchmarkRowDTO }) {
  return (
    <div className={styles.metaCell}>
      <ComparabilityIndicator
        value={row.comparability}
        sourceTransition={hasEstimatorTransition(row)}
        {...SUPERVISORY_TABLE_STATUS_TEXT}
      />
    </div>
  );
}

export function BenchmarkActionabilityCell({ row }: { row: BenchmarkRowDTO }) {
  const resolved = resolveTableActionability(row);
  return (
    <div className={styles.chipCell}>
      <ActionabilityPill value={resolved} {...SUPERVISORY_TABLE_STATUS_TEXT} />
    </div>
  );
}
