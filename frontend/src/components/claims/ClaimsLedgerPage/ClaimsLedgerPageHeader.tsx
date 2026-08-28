import { Link } from 'react-router-dom';
import { Typography } from '../../layout/Typography/Typography';

import { ClaimsLedgerExportFlow } from '../../../actions/ClaimsLedgerExportFlow';

import { CLAIMS_LEDGER_PAGE_COPY } from '../../../claims/copy';
import { COMMAND_CENTER_COPY } from '../../../commandCenter/copy';

import type { ClaimsFilters } from '../../../claims/claimsClient';

import detailStyles from '../../../detail/DetailReturnLink.module.css';
import shared from '../../../styles/shared.module.css';
import styles from './ClaimsLedgerPage.module.css';

export function ClaimsLedgerPageHeader({ filters }: { filters: ClaimsFilters }) {
  return (
    <div className={styles.headerRow} data-claims-ledger-header-row>
      {filters.trendDrill ? (
        <nav
          className={detailStyles.breadcrumb}
          aria-label="Breadcrumb"
          data-claims-trend-drill-breadcrumb
        >
          <Link to="/app" className={[detailStyles.breadcrumbLink, shared.focusVisible].join(' ')}>
            {COMMAND_CENTER_COPY.trendDrillBreadcrumb.commandCenter}
          </Link>
          <span className={detailStyles.breadcrumbSep} aria-hidden>
            /
          </span>
          <Link to="/app" className={[detailStyles.breadcrumbLink, shared.focusVisible].join(' ')}>
            {COMMAND_CENTER_COPY.trendDrillBreadcrumb.trend}
          </Link>
          <span className={detailStyles.breadcrumbSep} aria-hidden>
            /
          </span>
          <span className={detailStyles.breadcrumbCurrent}>
            {filters.trendWindowLabel ?? 'Snapshot window'}
          </span>
        </nav>
      ) : null}

      <header data-claims-ledger-header data-page-interface-header className={styles.pageHeaderStack}>

        <Typography variant="h1" className={styles.pageTitle}>

          {CLAIMS_LEDGER_PAGE_COPY.title}

        </Typography>

        <p className={styles.pageQuestion}>{CLAIMS_LEDGER_PAGE_COPY.subtitle}</p>

      </header>

      <div className={styles.headerActionColumn} data-claims-ledger-header-actions>

        <ClaimsLedgerExportFlow filters={filters} layout="header" />

      </div>

    </div>

  );

}

