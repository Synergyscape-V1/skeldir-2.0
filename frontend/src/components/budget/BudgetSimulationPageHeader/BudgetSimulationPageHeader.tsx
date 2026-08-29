import { IconInfo } from '../../icons/StatusIcons';
import { Typography } from '../../layout/Typography/Typography';
import { BUDGET_SIMULATION_COPY } from '../../../budget/copy';
import styles from './BudgetSimulationPageHeader.module.css';

export function BudgetSimulationPageHeader() {
  return (
    <>
      <div className={styles.headerRow} data-budget-header-row>
        <header
          className={styles.pageHeaderStack}
          data-budget-simulation-header
          data-page-interface-header
        >
          <Typography variant="h1" className={styles.pageTitle} id="budget-simulation-title" tabIndex={-1}>
            {BUDGET_SIMULATION_COPY.title}
          </Typography>
          <p className={styles.pageSubtitle}>{BUDGET_SIMULATION_COPY.subtitle}</p>
          <p className={styles.pageMetadata}>{BUDGET_SIMULATION_COPY.metadataLine}</p>
        </header>
      </div>
      <div className={styles.policyNotice} role="note" data-policy-boundary-notice>
        <IconInfo className={styles.policyNoticeIcon} aria-hidden="true" />
        <p className={styles.policyNoticeCopy}>{BUDGET_SIMULATION_COPY.policyBoundaryNotice}</p>
      </div>
    </>
  );
}
