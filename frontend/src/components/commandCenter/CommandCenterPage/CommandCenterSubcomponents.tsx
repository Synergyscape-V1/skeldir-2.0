import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { COMMAND_CENTER_COPY } from '../../../commandCenter/copy';
import { resolvePrimaryAction } from '../../../commandCenter/commandCenterClient';
import { canUseCommandCenterSupervisoryActions } from '../../../commandCenter/permissions';
import {
  beginTriageSession,
  countBlockingIssues,
  syncTriageIssues,
} from '../../../commandCenter/triageQueueStore';
import { useTriageQueue } from '../../../commandCenter/useTriageQueue';
import { getCurrentUserRole } from '../../../governance/governanceStore';
import { formatRelativeUpdatedTime } from '../../../lib/relativeTime';
import type { CommandCenterAggregate } from '../../../commandCenter/types';
import { Typography } from '../../layout/Typography/Typography';
import { PriorityQueueModal } from '../PriorityQueueModal/PriorityQueueModal';
import shared from '../../../styles/shared.module.css';
import styles from './CommandCenterSubcomponents.module.css';

export function CommandCenterPageHeader() {
  return (
    <header data-command-center-header data-page-interface-header className={styles.pageHeaderStack}>
      <Typography variant="h1" className={styles.pageTitle}>
        {COMMAND_CENTER_COPY.pageTitle}
      </Typography>
      <p className={styles.pageQuestion}>{COMMAND_CENTER_COPY.pageQuestion}</p>
    </header>
  );
}

export function CommandCenterHeaderMeta({
  issueCount,
  lastUpdatedIso,
  allClear = false,
}: {
  issueCount?: number;
  lastUpdatedIso?: string;
  allClear?: boolean;
}) {
  if (!lastUpdatedIso && !(issueCount != null && issueCount > 0) && !allClear) {
    return null;
  }

  return (
    <div className={styles.headerMetaStack} data-command-center-header-meta>
      {lastUpdatedIso ? (
        <p className={styles.pageLastUpdated} data-command-center-last-updated>
          {COMMAND_CENTER_COPY.lastUpdated(formatRelativeUpdatedTime(lastUpdatedIso))}
        </p>
      ) : null}
      {allClear ? (
        <p className={styles.urgencyClear} data-command-center-urgency data-urgency-all-clear role="status">
          {COMMAND_CENTER_COPY.urgencyAllClear}
        </p>
      ) : issueCount != null && issueCount > 0 ? (
        <p className={styles.urgency} data-command-center-urgency role="status">
          {COMMAND_CENTER_COPY.urgencyCopy(issueCount)}
        </p>
      ) : null}
    </div>
  );
}

export function PageScopedStatusText({ message }: { message: string }) {
  return (
    <p className={styles.statusText} data-command-center-status-text role="status" aria-live="polite">
      {message}
    </p>
  );
}

export function GlobalPrimaryActionButton({
  aggregate,
  unresolvedCount,
  onOpenQueue,
  triggerRef,
}: {
  aggregate: CommandCenterAggregate;
  unresolvedCount: number;
  onOpenQueue: () => void;
  triggerRef: React.RefObject<HTMLButtonElement | null>;
}) {
  const role = getCurrentUserRole();
  if (!canUseCommandCenterSupervisoryActions(role)) {
    return (
      <div
        data-command-center-primary-action
        data-primary-action-kind="read_only_restricted"
        data-viewer-read-only-supervisory
      >
        <p className={styles.meta}>{COMMAND_CENTER_COPY.viewerReadOnlySupervisory}</p>
        {unresolvedCount > 0 ? (
          <button
            ref={triggerRef}
            type="button"
            className={[styles.secondaryButton, shared.focusVisible].join(' ')}
            data-priority-queue-open
            data-priority-queue-open-readonly
            onClick={() => {
              beginTriageSession(aggregate.priorityIssues);
              onOpenQueue();
            }}
          >
            {COMMAND_CENTER_COPY.viewIssuesReadOnly(unresolvedCount)}
          </button>
        ) : null}
      </div>
    );
  }
  const action = resolvePrimaryAction(aggregate, unresolvedCount);

  if (action.kind === 'review_issues') {
    return (
      <div data-command-center-primary-action data-primary-action-kind={action.kind}>
        <button
          ref={triggerRef}
          type="button"
          className={[styles.primaryButton, shared.focusVisible].join(' ')}
          data-priority-queue-open
          onClick={() => {
            beginTriageSession(aggregate.priorityIssues);
            onOpenQueue();
          }}
        >
          {action.label}
        </button>
      </div>
    );
  }

  return (
    <div data-command-center-primary-action data-primary-action-kind={action.kind}>
      <Link to={action.href ?? '/app'} className={[styles.primaryButton, shared.focusVisible].join(' ')}>
        {action.label}
      </Link>
    </div>
  );
}

export function GlobalTrustApiErrorBanner({ message }: { message: string }) {
  return (
    <div
      className={styles.errorBanner}
      role="alert"
      aria-live="assertive"
      data-command-center-trust-api-error
    >
      {message}
    </div>
  );
}

export function KillSwitchReadOnlyBanner() {
  return (
    <div
      className={styles.warningBanner}
      role="status"
      aria-live="polite"
      data-command-center-kill-switch-banner
    >
      {COMMAND_CENTER_COPY.killSwitchReadOnly}
    </div>
  );
}

export function OnboardingContinuationPanel() {
  return (
    <section className={styles.panel} data-command-center-onboarding-panel>
      <Typography variant="h3">{COMMAND_CENTER_COPY.onboardingContinuationTitle}</Typography>
      <p>{COMMAND_CENTER_COPY.onboardingContinuationBody}</p>
      <Link to="/app/onboarding/step/1" className={[styles.secondaryButton, shared.focusVisible].join(' ')}>
        {COMMAND_CENTER_COPY.onboardingContinuationAction}
      </Link>
    </section>
  );
}

export function EmptyTenantPanel() {
  return (
    <section className={styles.warningBanner} role="alert" data-command-center-empty-tenant>
      {COMMAND_CENTER_COPY.emptyTenant}
    </section>
  );
}

export function SystemHealthStatusBanner({ healthState }: { healthState: string }) {
  const copy =
    healthState === 'confidence_degraded'
      ? COMMAND_CENTER_COPY.confidenceDegradedBanner
      : healthState === 'integration_attention'
        ? COMMAND_CENTER_COPY.integrationAttentionBanner
        : null;
  if (!copy) return null;
  return (
    <div
      className={styles.warningBanner}
      role="status"
      aria-live="polite"
      data-command-center-health-banner
      data-health-state={healthState}
    >
      {copy}
    </div>
  );
}

export function CommandCenterHeaderRow({ aggregate }: { aggregate: CommandCenterAggregate }) {
  const triage = useTriageQueue();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const unresolvedCount = countBlockingIssues(aggregate.priorityIssues, triage);
  const sessionCleared =
    triage.sessionActive &&
    aggregate.priorityIssues.length > 0 &&
    unresolvedCount === 0;

  const issueKey = aggregate.priorityIssues.map((issue) => issue.id).join('|');

  useEffect(() => {
    syncTriageIssues(aggregate.priorityIssues);
    // issueKey is the intentional equality signal; array identity is unstable.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- sync on id-set change only
  }, [issueKey]);

  return (
    <div className={styles.headerRow}>
      <CommandCenterPageHeader />
      <div className={styles.headerActionColumn} data-command-center-header-actions>
        <CommandCenterHeaderMeta
          issueCount={unresolvedCount}
          lastUpdatedIso={aggregate.lastUpdatedAt}
          allClear={sessionCleared}
        />
        <GlobalPrimaryActionButton
          aggregate={aggregate}
          unresolvedCount={unresolvedCount}
          onOpenQueue={() => setDrawerOpen(true)}
          triggerRef={triggerRef}
        />
      </div>
      <PriorityQueueModal
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        issues={aggregate.priorityIssues}
        triggerRef={triggerRef}
      />
    </div>
  );
}
