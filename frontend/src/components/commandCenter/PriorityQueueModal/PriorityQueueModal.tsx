import { useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';

import { COMMAND_CENTER_COPY } from '../../../commandCenter/copy';
import { COMMAND_CENTER_CHIP_PROPS } from '../../../commandCenter/commandCenterChipProps';
import { canUseCommandCenterSupervisoryActions } from '../../../commandCenter/permissions';
import { buildTriageHref } from '../../../commandCenter/triageHref';
import {
  beginTriageSession,
  isTriageIssueResolved,
} from '../../../commandCenter/triageQueueStore';
import { useTriageQueue } from '../../../commandCenter/useTriageQueue';
import { getCurrentUserRole } from '../../../governance/governanceStore';
import type { PriorityIssue } from '../../../commandCenter/types';
import { Modal } from '../../layout/Modal/Modal';
import { PolicyAuthorityPill } from '../../trust/PolicyAuthorityPill/PolicyAuthorityPill';
import shared from '../../../styles/shared.module.css';
import styles from './PriorityQueueModal.module.css';

export interface PriorityQueueModalProps {
  open: boolean;
  onClose: () => void;
  issues: PriorityIssue[];
  triggerRef?: React.RefObject<HTMLElement | null>;
}

/** @deprecated Use PriorityQueueModal — retained export alias for import stability. */
export type PriorityQueueDrawerProps = PriorityQueueModalProps;

export function PriorityQueueModal({ open, onClose, issues, triggerRef }: PriorityQueueModalProps) {
  const triage = useTriageQueue();
  const canAct = canUseCommandCenterSupervisoryActions(getCurrentUserRole());
  const nextUnresolvedRef = useRef<HTMLLIElement | null>(null);
  const unresolvedCount = issues.filter((issue) => !isTriageIssueResolved(issue.id, triage)).length;
  const issueKey = issues.map((issue) => issue.id).join('|');

  useEffect(() => {
    if (!open) return;
    beginTriageSession(issues);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- sync on open + id-set only
  }, [open, issueKey]);

  useEffect(() => {
    if (!open) return;
    const node = nextUnresolvedRef.current;
    if (node && typeof node.scrollIntoView === 'function') {
      node.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }, [open, triage.resolvedIds, triage.lastResolvedId]);

  return (
    <Modal
      open={open}
      onClose={onClose}
      triggerRef={triggerRef}
      title={COMMAND_CENTER_COPY.priorityDrawerTitle(unresolvedCount)}
      size="wide"
      closeOnBackdropClick
    >
      <div
        className={styles.root}
        data-priority-queue-modal
        data-priority-queue-drawer
        data-priority-queue-drawer-count={unresolvedCount}
        data-priority-queue-modal-count={unresolvedCount}
      >
        {issues.length === 0 ? (
          <p data-priority-queue-drawer-empty data-priority-queue-modal-empty>
            {COMMAND_CENTER_COPY.noPriorityIssues}
          </p>
        ) : (
          <ol className={styles.list} data-priority-queue-drawer-list data-priority-queue-modal-list>
            {issues.map((issue, index) => {
              const resolved = isTriageIssueResolved(issue.id, triage);
              const rank = index + 1;
              const href = buildTriageHref(issue.actionHref, issue.id, rank, issues.length);
              const isNext =
                !resolved &&
                issues.findIndex((row) => !isTriageIssueResolved(row.id, triage)) === index;

              return (
                <li
                  key={issue.id}
                  ref={isNext ? nextUnresolvedRef : undefined}
                  className={[styles.row, resolved ? styles.rowResolved : ''].filter(Boolean).join(' ')}
                  data-priority-drawer-issue={issue.id}
                  data-priority-modal-issue={issue.id}
                  data-priority-issue={issue.id}
                  data-priority-severity={issue.severity}
                  data-priority-subject-ref={issue.subjectRef}
                  data-priority-drawer-rank={rank}
                  data-priority-modal-rank={rank}
                  data-priority-drawer-resolved={resolved ? 'true' : 'false'}
                  data-priority-modal-resolved={resolved ? 'true' : 'false'}
                  data-priority-resolved={resolved ? 'true' : 'false'}
                  data-priority-drawer-next={isNext ? 'true' : undefined}
                  data-priority-modal-next={isNext ? 'true' : undefined}
                  {...(index === 0 ? { 'data-top-priority-issue': issue.id } : {})}
                >
                  <div className={styles.body}>
                    <div className={styles.pillRow}>
                      <PolicyAuthorityPill
                        state={issue.policyAuthority}
                        {...COMMAND_CENTER_CHIP_PROPS}
                        appearance="text"
                      />
                    </div>
                    <strong className={styles.title}>{issue.title}</strong>
                    <p className={styles.explanation}>{issue.explanation}</p>
                  </div>

                  <div className={styles.action}>
                    {resolved ? (
                      <span
                        className={styles.approved}
                        data-priority-drawer-approved
                        data-priority-modal-approved
                      >
                        {COMMAND_CENTER_COPY.priorityIssueApproved}
                      </span>
                    ) : canAct ? (
                      <Link
                        to={href}
                        className={[styles.actionLink, shared.focusVisible].join(' ')}
                        data-priority-drawer-action
                        data-priority-modal-action
                        data-priority-action-href={href}
                        onClick={onClose}
                      >
                        {issue.actionLabel}
                      </Link>
                    ) : (
                      <Link
                        to={issue.sourceLink}
                        className={[styles.actionLink, shared.focusVisible].join(' ')}
                        data-priority-drawer-source
                        data-priority-modal-source
                        onClick={onClose}
                      >
                        {COMMAND_CENTER_COPY.viewSourceEvidence}
                      </Link>
                    )}
                  </div>
                </li>
              );
            })}
          </ol>
        )}
        {triage.lastToast ? (
          <p className={styles.toast} role="status" aria-live="polite" data-priority-queue-toast>
            {triage.lastToast}
          </p>
        ) : null}
      </div>
    </Modal>
  );
}

/** @deprecated Prefer PriorityQueueModal */
export const PriorityQueueDrawer = PriorityQueueModal;
