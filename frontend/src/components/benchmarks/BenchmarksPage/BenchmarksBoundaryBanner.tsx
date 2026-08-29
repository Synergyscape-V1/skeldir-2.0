import { BENCHMARKS_COPY } from '../../../benchmarks/copy';
import styles from './BenchmarksBoundaryBanner.module.css';

export function BenchmarksBoundaryBanner() {
  return (
    <div className={styles.banner} data-benchmarks-boundary-banner role="note">
      <p className={styles.copy}>{BENCHMARKS_COPY.boundaryBanner}</p>
    </div>
  );
}