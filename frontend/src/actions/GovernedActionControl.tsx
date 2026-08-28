import type { ReactNode, RefObject } from 'react';
import { Modal } from '../components/layout/Modal/Modal';
import { Toast } from '../components/layout/Toast/Toast';
import { PolicyAuthorityPill } from '../components/trust/PolicyAuthorityPill/PolicyAuthorityPill';
import type { PolicyAuthorityState } from '../lib/types';
import shared from '../styles/shared.module.css';
import type { ActionFlowPhase, GovernedActionOutcome } from './types';
import styles from './GovernedActionControl.module.css';

export interface GovernedActionControlProps {
  actionLabel: string;
  policyAuthority: PolicyAuthorityState;
  disabled: boolean;
  disabledReason?: string;
  phase: ActionFlowPhase;
  outcome: GovernedActionOutcome | null;
  confirmationTitle: string;
  confirmationBody: ReactNode;
  destructive?: boolean;
  triggerRef?: RefObject<HTMLButtonElement | null>;
  triggerClassName?: string;
  leadingIcon?: ReactNode;
  onOpen: () => void;
  onConfirm: () => void;
  onCancel: () => void;
  onDismissToast: () => void;
  showToast: boolean;
  policyCopyInModal?: string;
  outcomeVisibility?: 'visible' | 'sr-only';
  showOutcomeDetails?: boolean;
  align?: 'start' | 'end';
  toastShowProgress?: boolean;
  pendingLabel?: string;
  /** Plain-English Pass/Fail treatment for signature verification (Mode B). */
  binaryVerdict?: boolean;
}

export function GovernedActionControl({
  actionLabel,
  policyAuthority,
  disabled,
  disabledReason,
  phase,
  outcome,
  confirmationTitle,
  confirmationBody,
  destructive = true,
  triggerRef,
  triggerClassName,
  leadingIcon,
  onOpen,
  onConfirm,
  onCancel,
  onDismissToast,
  showToast,
  policyCopyInModal,
  outcomeVisibility = 'visible',
  showOutcomeDetails = true,
  align = 'start',
  toastShowProgress = false,
  pendingLabel,
  binaryVerdict = false,
}: GovernedActionControlProps) {
  const toastMessage = outcome?.safeUserCopy ?? disabledReason;
  const toastSeverity =
    outcome?.status === 'success' ? 'success' : outcome?.status ? 'error' : 'info';
  const verdictTone =
    outcome?.status === 'success' ? 'pass' : outcome?.status ? 'fail' : undefined;

  return (
    <div
      className={[styles.root, align === 'end' ? styles.rootAlignEnd : ''].filter(Boolean).join(' ')}
      data-governed-action-control
    >
      <button
        ref={triggerRef}
        type="button"
        className={[triggerClassName || styles.button, shared.focusVisible].filter(Boolean).join(' ')}
        data-level9-action
        data-level9-phase={phase}
        aria-label={disabled && disabledReason ? `${actionLabel}. ${disabledReason}` : actionLabel}
        aria-describedby={disabledReason ? `l9-disabled-${actionLabel.replace(/\s+/g, '-')}` : undefined}
        aria-busy={phase === 'pending'}
        disabled={disabled}
        onClick={onOpen}
      >
        {leadingIcon}
        {phase === 'pending' ? (pendingLabel ?? `${actionLabel}…`) : actionLabel}
      </button>
      {disabledReason ? (
        <span id={`l9-disabled-${actionLabel.replace(/\s+/g, '-')}`} className={styles.srOnly}>
          {disabledReason}
        </span>
      ) : null}

      <Modal
        open={phase === 'confirmation_open'}
        onClose={onCancel}
        triggerRef={triggerRef}
        title={confirmationTitle}
        type={destructive ? 'destructive' : 'standard'}
        confirmLabel={actionLabel}
        onConfirm={onConfirm}
      >
        <div data-level9-confirmation>
          <PolicyAuthorityPill state={policyAuthority} />
          {policyCopyInModal ? <p>{policyCopyInModal}</p> : null}
          <div className={styles.confirmBody}>{confirmationBody}</div>
        </div>
      </Modal>

      {outcome ? (
        <div
          className={[
            styles.outcome,
            outcomeVisibility === 'sr-only' ? styles.outcomeSrOnly : '',
            binaryVerdict ? styles.binaryVerdict : '',
            binaryVerdict && verdictTone === 'pass' ? styles.binaryVerdictPass : '',
            binaryVerdict && verdictTone === 'fail' ? styles.binaryVerdictFail : '',
          ]
            .filter(Boolean)
            .join(' ')}
          data-level9-outcome
          data-level9-outcome-status={outcome.status}
          data-level9-outcome-visibility={outcomeVisibility}
          data-binary-verdict={binaryVerdict ? verdictTone : undefined}
          role="status"
          aria-live={binaryVerdict && verdictTone === 'fail' ? 'assertive' : 'polite'}
        >
          <p>{outcome.safeUserCopy}</p>
          {showOutcomeDetails && !binaryVerdict && outcome.actionId ? (
            <p className={styles.outcomeDetail} data-level9-outcome-action-id>
              Action: {outcome.actionId}
            </p>
          ) : null}
          {showOutcomeDetails && !binaryVerdict && outcome.auditEventId ? (
            <p className={styles.outcomeDetail} data-level9-outcome-audit-id>
              Audit: {outcome.auditEventId}
            </p>
          ) : null}
          {showOutcomeDetails && !binaryVerdict && outcome.artifactRef ? (
            <p className={styles.outcomeDetail}>Artifact: {outcome.artifactRef}</p>
          ) : null}
          {showOutcomeDetails && !binaryVerdict && outcome.proposalId ? (
            <p className={styles.outcomeDetail}>Proposal: {outcome.proposalId}</p>
          ) : null}
        </div>
      ) : null}

      {showToast && toastMessage ? (
        <Toast
          severity={toastSeverity}
          message={toastMessage}
          open={showToast}
          onDismiss={onDismissToast}
          showProgress={toastShowProgress && toastSeverity === 'success'}
        />
      ) : null}
    </div>
  );
}
