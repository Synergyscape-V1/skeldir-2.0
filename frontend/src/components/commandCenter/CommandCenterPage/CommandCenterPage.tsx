import { PageSurface } from '../../layout/PageSurface/PageSurface';
import { Skeleton } from '../../layout/Skeleton/Skeleton';
import { PermissionDeniedPanel } from '../../governance/PermissionDeniedPanel/PermissionDeniedPanel';
import { COMMAND_CENTER_COPY } from '../../../commandCenter/copy';
import { useCommandCenter } from '../../../commandCenter/useCommandCenter';
import {
  AuditActivityStrip,
  ChannelTrustTableCard,
  RecentTrustEnvelopesCard,
  TrustStateSummaryRow,
  VerifiedRevenueTrendCard,
} from './CommandCenterSections';
import {
  CommandCenterHeaderRow,
  GlobalTrustApiErrorBanner,
  KillSwitchReadOnlyBanner,
  OnboardingContinuationPanel,
  EmptyTenantPanel,
  SystemHealthStatusBanner,
  PageScopedStatusText,
  CommandCenterPageHeader,
} from './CommandCenterSubcomponents';
import type { CommandCenterAggregate, CommandCenterOutcome } from '../../../commandCenter/types';
import styles from './CommandCenterPage.module.css';
import subStyles from './CommandCenterSubcomponents.module.css';

function shouldShowCommandCenterBanners(
  aggregate: CommandCenterAggregate,
  outcome: CommandCenterOutcome | null,
): boolean {
  if (aggregate.killSwitchActive) return true;
  if (
    aggregate.healthState === 'confidence_degraded' ||
    aggregate.healthState === 'integration_attention'
  ) {
    return true;
  }
  return outcome?.kind === 'stale' || outcome?.kind === 'partial';
}

export function CommandCenterPage() {
  const { outcome, aggregate, loading, loadingPhase, retry } = useCommandCenter();

  if (outcome?.kind === 'permission_denied') {
    return (
      <PageSurface className={styles.permissionDenied} data-command-center-page>
        <PermissionDeniedPanel recoveryHref="/app/settings/team" />
      </PageSurface>
    );
  }

  if (outcome?.kind === 'empty_tenant') {
    return (
      <PageSurface data-command-center-page data-command-center-empty-tenant="true">
        <CommandCenterPageHeader />
        <EmptyTenantPanel />
      </PageSurface>
    );
  }

  if (outcome?.kind === 'trust_api_read_failed') {
    return (
      <PageSurface className={styles.CommandCenterPage} data-command-center-page>
        <CommandCenterPageHeader />
        <GlobalTrustApiErrorBanner message={outcome.message} />
        <button type="button" onClick={retry} className={styles.retryButton} data-command-center-retry>
          {COMMAND_CENTER_COPY.retryAggregate}
        </button>
      </PageSurface>
    );
  }

  if (loading && !aggregate) {
    return (
      <PageSurface data-command-center-page data-command-center-loading="true">
        <CommandCenterPageHeader />
        <div className={subStyles.loadingSkeletonGrid} aria-busy="true">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={`card-${i}`} className={subStyles.skeletonBlock} />
          ))}
        </div>
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={`row-${i}`} className={subStyles.loadingSkeletonRow} />
        ))}
        {loadingPhase === 'over_2s' ? (
          <p role="status">{COMMAND_CENTER_COPY.loadingProgress}</p>
        ) : null}
        {loadingPhase === 'over_8s' ? (
          <button type="button" onClick={retry} data-command-center-loading-retry>
            {COMMAND_CENTER_COPY.retryAggregate}
          </button>
        ) : null}
      </PageSurface>
    );
  }

  if (!aggregate) {
    return (
      <PageSurface data-command-center-page>
        <CommandCenterPageHeader />
        <OnboardingContinuationPanel />
      </PageSurface>
    );
  }

  return (
    <PageSurface className={styles.CommandCenterPage} data-command-center-page data-command-center-loaded="true">
      {shouldShowCommandCenterBanners(aggregate, outcome) ? (
        <div className={styles.banners}>
          {aggregate.killSwitchActive ? <KillSwitchReadOnlyBanner /> : null}
          <SystemHealthStatusBanner healthState={aggregate.healthState} />
          {outcome?.kind === 'stale' ? (
            <PageScopedStatusText message={outcome.message} />
          ) : null}
          {outcome?.kind === 'partial' ? (
            <PageScopedStatusText message={outcome.message} />
          ) : null}
        </div>
      ) : null}

      <CommandCenterHeaderRow aggregate={aggregate} />

      <div className={styles.contentRail} data-page-content-rail>
        {!aggregate.hasTrustEnvelope ? <OnboardingContinuationPanel /> : null}

        <TrustStateSummaryRow aggregate={aggregate} />

        <div className={styles.proofSurfaceBand} data-proof-surface-band>
          <div className={styles.proofSurfaceTopRow} data-grid-trend-table>
            <VerifiedRevenueTrendCard aggregate={aggregate} />
            <AuditActivityStrip aggregate={aggregate} />
          </div>

          <div className={styles.proofChannelSlot} data-channel-trust-band data-grid-dual-panel>
            <ChannelTrustTableCard aggregate={aggregate} />
          </div>

          <div className={styles.proofEnvelopesSlot} data-recent-envelopes-band>
            <RecentTrustEnvelopesCard aggregate={aggregate} />
          </div>
        </div>
      </div>
    </PageSurface>
  );
}
