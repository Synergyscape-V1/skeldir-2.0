import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { getAuthState } from '../auth/sessionStore';
import { getCurrentUserRole } from '../governance/governanceStore';
import { formatMoneyMinorDisplayWithCents, parseMoneyMinor } from '../lib/money';
import { ACTION_COPY } from './copy';
import { getDefaultBudgetProposalClient, submitBudgetProposal } from './budgetProposalClient';
import { buildActionFingerprint } from './idempotency';
import { hasActionPermission } from './permissions';
import { checkSubsystemSafetyForExternalAction } from './systemSafety';
import { GovernedActionControl } from './GovernedActionControl';
import { useGovernedAction } from './useGovernedAction';
import type { BudgetProposalPreview } from './types';
import type { PolicyAuthorityState } from '../lib/types';
import styles from './BudgetProposalFlow.module.css';

export interface BudgetProposalFlowProps {
  simulationId: string;
  versionStamp: string;
  policyAuthority: PolicyAuthorityState;
  triageMode?: boolean;
  onTriageSuccess?: () => void;
}

function formatPreviewRevenue(minorRaw: string, currencyCode: string): {
  ok: true;
  display: string;
} | {
  ok: false;
  reason: string;
} {
  const parsed = parseMoneyMinor(minorRaw);
  if (!parsed.ok) {
    return { ok: false, reason: 'Verified revenue basis is unavailable for display.' };
  }
  return {
    ok: true,
    display: formatMoneyMinorDisplayWithCents(parsed.value, currencyCode),
  };
}

export function BudgetProposalFlow({
  simulationId,
  versionStamp,
  policyAuthority,
  triageMode = false,
  onTriageSuccess,
}: BudgetProposalFlowProps) {
  const [preview, setPreview] = useState<BudgetProposalPreview | null>(null);
  const [subsystemSafe, setSubsystemSafe] = useState(true);
  const [subsystemCopy, setSubsystemCopy] = useState<string>();
  const [showToast, setShowToast] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const triageSuccessNotified = useRef(false);
  const { tenant } = getAuthState();
  const tenantId = tenant?.tenantId ?? '';

  useEffect(() => {
    void getDefaultBudgetProposalClient().buildProposalPreview(tenantId, simulationId).then(setPreview);
    void checkSubsystemSafetyForExternalAction(tenantId).then((s) => {
      setSubsystemSafe(s.safe);
      setSubsystemCopy(s.copy);
    });
  }, [tenantId, simulationId]);

  const revenueDisplay = useMemo(() => {
    if (!preview) return null;
    return formatPreviewRevenue(preview.verifiedRevenueBasisMinor, preview.currencyCode);
  }, [preview]);

  const onExecute = useCallback(
    (idempotencyKey: string) => submitBudgetProposal(tenantId, simulationId, versionStamp, idempotencyKey),
    [tenantId, simulationId, versionStamp],
  );

  const action = useGovernedAction({
    tenantId,
    objectId: simulationId,
    objectType: 'budget_simulation',
    actionFingerprint: buildActionFingerprint(tenantId, 'budget_simulation', simulationId, 'submit_proposal'),
    policyAuthority,
    consequence: 'workflow_mutation',
    permissionOk: hasActionPermission(getCurrentUserRole(), 'submit_budget_proposal'),
    permissionDeniedCopy: ACTION_COPY.permissionDenied,
    subsystemSafe,
    subsystemCopy,
    onExecute,
  });

  useEffect(() => {
    if (!triageMode || !onTriageSuccess) return;
    if (action.phase === 'success' && action.outcome?.status === 'success' && !triageSuccessNotified.current) {
      triageSuccessNotified.current = true;
      onTriageSuccess();
    }
  }, [triageMode, onTriageSuccess, action.phase, action.outcome]);

  const actionLabel = triageMode ? 'Approve & Advance' : 'Submit proposal';
  const pendingLabel = triageMode ? 'Authorizing policy...' : undefined;

  const formattedRevenue = revenueDisplay?.ok ? revenueDisplay.display : null;
  const revenueUnavailable = revenueDisplay !== null && !revenueDisplay.ok;

  return (
    <div data-budget-proposal-flow data-budget-proposal-triage={triageMode ? 'true' : 'false'}>
      {preview ? (
        <div className={styles.preview} data-proposal-preview>
          <h3 className={styles.previewTitle}>Proposal preview</h3>
          <dl className={styles.previewFacts}>
            <div className={styles.previewFact}>
              <dt>Verified revenue basis</dt>
              <dd
                data-proposal-verified-revenue
                data-proposal-revenue-format={formattedRevenue ? 'locale-currency' : 'unavailable'}
              >
                {formattedRevenue ? (
                  <>
                    <span data-proposal-revenue-display>{formattedRevenue}</span>
                    <span className={styles.currencyMeta}>{preview.currencyCode}</span>
                  </>
                ) : (
                  <span role="status">{revenueDisplay && !revenueDisplay.ok ? revenueDisplay.reason : null}</span>
                )}
              </dd>
            </div>
          </dl>
          <p>{preview.confidenceCaveat}</p>
          <p>{preview.benchmarkContext}</p>
          <ul>
            {preview.riskCaveats.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
          <p data-no-spend-mutation>No spend mutation. Proposal only.</p>
        </div>
      ) : null}
      <GovernedActionControl
        actionLabel={actionLabel}
        pendingLabel={pendingLabel}
        policyAuthority={policyAuthority}
        disabled={action.disabled || revenueUnavailable}
        disabledReason={
          revenueUnavailable
            ? 'Verified revenue basis could not be formatted for confirmation.'
            : action.disabledReason
        }
        phase={action.phase}
        outcome={action.outcome}
        confirmationTitle={triageMode ? 'Approve budget policy' : 'Submit budget proposal'}
        confirmationBody={
          <div data-proposal-confirmation-gate>
            {formattedRevenue ? (
              <p data-proposal-confirmation-revenue>
                Confirm verified revenue basis <strong>{formattedRevenue}</strong> ({preview?.currencyCode}).
              </p>
            ) : (
              <p role="status">Verified revenue basis is unavailable — submission is blocked.</p>
            )}
            <p>
              {triageMode
                ? 'Authorizes this simulation under tenant policy, then advances to the next blocking issue. No auto-optimize and no guaranteed lift.'
                : 'Creates a governed proposal for review. No budget applied, no auto-optimize, and no guaranteed lift.'}
            </p>
            <p data-no-spend-mutation>No spend mutation. Proposal only.</p>
          </div>
        }
        triggerRef={triggerRef}
        onOpen={() => {
          if (revenueUnavailable) return;
          action.openConfirmation();
          setShowToast(false);
        }}
        onConfirm={() => {
          action.confirm();
          setShowToast(!triageMode);
        }}
        onCancel={action.cancel}
        showToast={showToast && action.outcome !== null && !triageMode}
        onDismissToast={() => setShowToast(false)}
      />
    </div>
  );
}
