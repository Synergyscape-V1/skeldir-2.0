import type { BenchmarkShape } from '../../../ledger/types';
import { AuthorityBadge } from '../../trust/AuthorityBadge/AuthorityBadge';
import { DataUnavailablePanel } from '../../trust/DataUnavailablePanel/DataUnavailablePanel';
import { BENCHMARKS_COPY } from '../../../benchmarks/copy';
import { formatBenchmarkValue } from '../../../benchmarks/benchmarkDisplay';
import styles from './BenchmarkCell.module.css';

export function BenchmarkCell({ benchmark }: { benchmark: BenchmarkShape }) {
  if (benchmark.status === 'unavailable') {
    return (
      <div data-benchmark-cell="unavailable">
        <DataUnavailablePanel
          variant="no_benchmark"
          reason={benchmark.reason ?? BENCHMARKS_COPY.table.unavailableSegmentCopy}
        />
      </div>
    );
  }

  if (benchmark.status === 'suppressed') {
    return (
      <div data-benchmark-cell="suppressed">
        <AuthorityBadge authority="suppressed" />
        <p className={styles.reason}>
          {benchmark.suppressionReason ?? BENCHMARKS_COPY.table.unavailableSegmentCopy}
        </p>
      </div>
    );
  }

  return (
    <div data-benchmark-cell="available" className={styles.available}>
      {benchmark.rawBenchmark ? (
        <span className={styles.value} data-benchmark-raw>
          Raw: {formatBenchmarkValue(benchmark.rawBenchmark)}
        </span>
      ) : null}
      {benchmark.decisionSafeBenchmark ? (
        <span className={styles.valueStrong} data-benchmark-decision-safe>
          Decision-safe: {formatBenchmarkValue(benchmark.decisionSafeBenchmark)}
        </span>
      ) : null}
      {benchmark.sourceTransition || benchmark.comparability === 'source_changed' ? (
        <span className={styles.transition} role="status">
          {BENCHMARKS_COPY.table.estimatorTransitionBadge} — {BENCHMARKS_COPY.table.estimatorTransitionTooltip}
        </span>
      ) : null}
    </div>
  );
}
