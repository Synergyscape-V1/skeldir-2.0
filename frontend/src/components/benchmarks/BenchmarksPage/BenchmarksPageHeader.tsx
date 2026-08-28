import { BENCHMARKS_COPY } from '../../../benchmarks/copy';
import { Typography } from '../../layout/Typography/Typography';
import styles from './BenchmarksPage.module.css';

export function BenchmarksPageHeader() {
  return (
    <header data-benchmarks-header className={styles.pageHeaderStack}>
      <Typography variant="h1" className={styles.pageTitle}>
        {BENCHMARKS_COPY.title}
      </Typography>
      <p className={styles.pageSubtitle}>{BENCHMARKS_COPY.subtitle}</p>
    </header>
  );
}
