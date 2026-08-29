import { IconInfo } from '../../icons/StatusIcons';
import { POLICY_AUTHORITY_EXPLANATION } from '../../../lib/policyAuthorityLabels';
import { BUDGET_SUFFICIENCY_THRESHOLDS } from '../../../budget/budgetFixtures';
import { PolicyAuthorityPill } from '../../trust/PolicyAuthorityPill/PolicyAuthorityPill';
import styles from './BudgetBlockedSparseDataPanel.module.css';

export interface BudgetBlockedSparseDataPanelProps {
  channelsAvailable: number;
  verifiedConversionsAvailable: number;
  loading?: boolean;
}

export function BudgetBlockedSparseDataPanel({
  channelsAvailable,
  verifiedConversionsAvailable,
  loading = false,
}: BudgetBlockedSparseDataPanelProps) {
  const { minimumChannels, minimumVerifiedConversions } = BUDGET_SUFFICIENCY_THRESHOLDS;

  if (loading) {
    return (
      <section
        className={styles.panel}
        role="status"
        aria-busy="true"
        data-blocked-sparse-data-panel
        data-loading="true"
      >
        <div className={styles.skeleton}>
          <div className={styles.skeletonIcon} />
          <div className={styles.skeletonContent}>
            <div className={styles.skeletonTitle} />
            <div className={styles.skeletonLine} />
            <div className={styles.skeletonGrid}>
              <div className={styles.skeletonItem} />
              <div className={styles.skeletonItem} />
              <div className={styles.skeletonItem} />
            </div>
          </div>
        </div>
      </section>
    );
  }

  const channelsGap = minimumChannels - channelsAvailable;
  const conversionsGap = minimumVerifiedConversions - verifiedConversionsAvailable;

  return (
    <section
      className={styles.panel}
      role="alert"
      tabIndex={-1}
      data-blocked-sparse-data-panel
    >
      <IconInfo className={styles.icon} aria-hidden="true" />
      <div className={styles.content}>
        <p className={styles.copy}>{POLICY_AUTHORITY_EXPLANATION.blockedSparse}</p>
        
        <div className={styles.gapSummary}>
          {channelsGap > 0 && (
            <div className={styles.gapItem}>
              <span className={styles.gapLabel}>Add {channelsGap} more channel{channelsGap > 1 ? 's' : ''}</span>
              <span className={styles.gapSublabel}>to meet minimum requirement</span>
            </div>
          )}
          {conversionsGap > 0 && (
            <div className={styles.gapItem}>
              <span className={styles.gapLabel}>Add {conversionsGap} more verified conversion{conversionsGap > 1 ? 's' : ''}</span>
              <span className={styles.gapSublabel}>to meet minimum requirement</span>
            </div>
          )}
        </div>

        <dl className={styles.details}>
          <div>
            <dt>Minimum channels required</dt>
            <dd>{minimumChannels}</dd>
          </div>
          <div>
            <dt>Channels available</dt>
            <dd className={styles.deficit}>{channelsAvailable}</dd>
          </div>
          <div>
            <dt>Minimum verified conversions required</dt>
            <dd>{minimumVerifiedConversions}</dd>
          </div>
          <div>
            <dt>Verified conversions available</dt>
            <dd className={styles.deficit}>{verifiedConversionsAvailable}</dd>
          </div>
          <div className={styles.policyRow}>
            <dt>Action authority</dt>
            <dd>
              <PolicyAuthorityPill state="blocked" size="table" />
            </dd>
          </div>
        </dl>
      </div>
    </section>
  );
}
