import { EXCEPTIONS_PAGE_COPY } from '../../../exceptions/copy';
import { Typography } from '../../layout/Typography/Typography';
import styles from '../ExceptionsQueuePage/ExceptionsQueuePage.module.css';

export function ExceptionsPageHeader() {
  return (
    <div className={styles.headerRow} data-exceptions-header-row>
      <header data-exceptions-header data-page-interface-header className={styles.pageHeaderStack}>
        <Typography variant="h1" className={styles.pageTitle}>
          {EXCEPTIONS_PAGE_COPY.title}
        </Typography>
        <p className={styles.pageSubtitle}>{EXCEPTIONS_PAGE_COPY.subtitle}</p>
      </header>
    </div>
  );
}
