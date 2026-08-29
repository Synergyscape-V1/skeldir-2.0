import { useCallback, useEffect, useRef, useState } from 'react';
import { getAuthState } from '../auth/sessionStore';
import { getCurrentUserRole } from '../governance/governanceStore';
import { ACTION_COPY } from './copy';
import {
  acknowledgeException,
  createProposal,
  getDefaultExceptionActionClient,
  markDisputed,
  requestMoreEvidence,
  suppressSimilarAlerts,
} from './exceptionActionClient';
import { buildActionFingerprint } from './idempotency';
import type { ExceptionActionKind } from './types';
import { hasActionPermission } from './permissions';
import { checkSubsystemSafetyForExternalAction } from './systemSafety';
import { GovernedActionControl } from './GovernedActionControl';
import { useGovernedAction } from './useGovernedAction';
import type { PolicyAuthorityState } from '../lib/types';
import styles from './ExceptionActionControls.module.css';

const ACTION_HANDLERS: Record<
  ExceptionActionKind,
  (tenantId: string, exceptionId: string, versionStamp: string, key: string) => ReturnType<typeof acknowledgeException>
> = {
  acknowledge: acknowledgeException,
  request_more_evidence: requestMoreEvidence,
  mark_disputed: markDisputed,
  suppress_similar: suppressSimilarAlerts,
  create_proposal: createProposal,
};

function ExceptionActionButton({
  kind,
  appearance,
  exceptionId,
  versionStamp,
  policyAuthority,
}: {
  kind: ExceptionActionKind;
  appearance: 'primary' | 'secondary' | 'quiet';
  exceptionId: string;
  versionStamp: string;
  policyAuthority: PolicyAuthorityState;
}) {
  const copy = getDefaultExceptionActionClient().getActionCopy(kind);
  const [subsystemSafe, setSubsystemSafe] = useState(true);
  const [subsystemCopy, setSubsystemCopy] = useState<string>();
  const [showToast, setShowToast] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const { tenant } = getAuthState();
  const tenantId = tenant?.tenantId ?? '';

  useEffect(() => {
    void checkSubsystemSafetyForExternalAction(tenantId).then((s) => {
      setSubsystemSafe(s.safe);
      setSubsystemCopy(s.copy);
    });
  }, [tenantId]);

  const onExecute = useCallback(
    (idempotencyKey: string) => ACTION_HANDLERS[kind](tenantId, exceptionId, versionStamp, idempotencyKey),
    [kind, tenantId, exceptionId, versionStamp],
  );

  const action = useGovernedAction({
    tenantId,
    objectId: exceptionId,
    objectType: 'exception',
    actionFingerprint: buildActionFingerprint(tenantId, 'exception', exceptionId, kind),
    policyAuthority,
    consequence: 'workflow_mutation',
    permissionOk: hasActionPermission(getCurrentUserRole(), 'perform_exception_action'),
    permissionDeniedCopy: ACTION_COPY.permissionDenied,
    subsystemSafe,
    subsystemCopy,
    onExecute,
  });

  return (
    <GovernedActionControl
      actionLabel={copy.label}
      policyAuthority={policyAuthority}
      disabled={action.disabled}
      disabledReason={action.disabledReason}
      phase={action.phase}
      outcome={action.outcome}
      confirmationTitle={copy.label}
      confirmationBody={<p>{copy.confirm}</p>}
      triggerRef={triggerRef}
      triggerClassName={
        appearance === 'primary'
          ? styles.primaryAction
          : appearance === 'secondary'
            ? styles.secondaryAction
            : styles.quietAction
      }
      onOpen={() => {
        action.openConfirmation();
        setShowToast(false);
      }}
      onConfirm={() => {
        action.confirm();
        setShowToast(true);
      }}
      onCancel={action.cancel}
      showToast={showToast && action.outcome !== null}
      onDismissToast={() => setShowToast(false)}
    />
  );
}

export interface ExceptionActionControlsProps {
  exceptionId: string;
  versionStamp: string;
  policyAuthority: PolicyAuthorityState;
}

export function ExceptionActionControls({
  exceptionId,
  versionStamp,
  policyAuthority,
}: ExceptionActionControlsProps) {
  return (
    <section
      className={styles.actionPanel}
      aria-labelledby="exception-response-heading"
      data-exception-action-controls
    >
      <header className={styles.panelHeader}>
        <h3 id="exception-response-heading" className={styles.panelHeading}>
          {ACTION_COPY.exceptionActionsHeading}
        </h3>
        <p className={styles.panelIntro}>{ACTION_COPY.exceptionActionsIntro}</p>
      </header>

      <div className={styles.primaryRow} data-exception-action-group="complete-review">
        <div className={styles.groupCopy}>
          <h4 className={styles.groupHeading}>{ACTION_COPY.completeReviewHeading}</h4>
          <p className={styles.groupBody}>{ACTION_COPY.completeReviewBody}</p>
        </div>
        <ExceptionActionButton
          kind="acknowledge"
          appearance="primary"
          exceptionId={exceptionId}
          versionStamp={versionStamp}
          policyAuthority={policyAuthority}
        />
      </div>

      <div className={styles.actionGroup} data-exception-action-group="continue-investigation">
        <div className={styles.groupCopy}>
          <h4 className={styles.groupHeading}>{ACTION_COPY.continueInvestigationHeading}</h4>
          <p className={styles.groupBody}>{ACTION_COPY.continueInvestigationBody}</p>
        </div>
        <div className={styles.buttonGrid}>
          {(['request_more_evidence', 'mark_disputed'] as const).map((kind) => (
            <ExceptionActionButton
              key={kind}
              kind={kind}
              appearance="secondary"
              exceptionId={exceptionId}
              versionStamp={versionStamp}
              policyAuthority={policyAuthority}
            />
          ))}
        </div>
      </div>

      <div className={styles.followUpGroup} data-exception-action-group="governed-follow-up">
        <div className={styles.groupCopy}>
          <h4 className={styles.groupHeading}>{ACTION_COPY.governedFollowUpHeading}</h4>
          <p className={styles.groupBody}>{ACTION_COPY.governedFollowUpBody}</p>
        </div>
        <div className={styles.buttonGrid}>
          {(['suppress_similar', 'create_proposal'] as const).map((kind) => (
            <ExceptionActionButton
              key={kind}
              kind={kind}
              appearance="quiet"
              exceptionId={exceptionId}
              versionStamp={versionStamp}
              policyAuthority={policyAuthority}
            />
          ))}
        </div>
      </div>
    </section>
  );
}
