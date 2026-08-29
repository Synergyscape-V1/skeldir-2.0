import { useCallback, useEffect, useRef, useState } from 'react';
import { getAuthState } from '../auth/sessionStore';
import { getCurrentUserRole } from '../governance/governanceStore';
import { AuthorityBadge } from '../components/trust/AuthorityBadge/AuthorityBadge';
import { ACTION_COPY } from './copy';
import { exportVerifiedReport } from './claimExportClient';
import { buildActionFingerprint } from './idempotency';
import { hasActionPermission } from './permissions';
import { checkSubsystemSafetyForExternalAction } from './systemSafety';
import { GovernedActionControl } from './GovernedActionControl';
import { useGovernedAction } from './useGovernedAction';
import type { ClaimExportPreview } from './types';
import { getDefaultClaimExportClient } from './claimExportClient';
import type { PolicyAuthorityState } from '../lib/types';
import styles from './ClaimExportFlow.module.css';

export interface ClaimExportFlowProps {
  claimId: string;
  versionStamp: string;
  policyAuthority: PolicyAuthorityState;
}

export function ClaimExportFlow({ claimId, versionStamp, policyAuthority }: ClaimExportFlowProps) {
  const [preview, setPreview] = useState<ClaimExportPreview | null>(null);
  const [subsystemSafe, setSubsystemSafe] = useState(true);
  const [subsystemCopy, setSubsystemCopy] = useState<string>();
  const [showToast, setShowToast] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const { tenant } = getAuthState();
  const tenantId = tenant?.tenantId ?? '';

  useEffect(() => {
    void getDefaultClaimExportClient().buildExportPreview(tenantId, claimId).then((result) => {
      if (result.ok) setPreview(result.preview);
    });
    void checkSubsystemSafetyForExternalAction(tenantId).then((s) => {
      setSubsystemSafe(s.safe);
      setSubsystemCopy(s.copy);
    });
  }, [tenantId, claimId]);

  const onExecute = useCallback(
    (idempotencyKey: string) =>
      exportVerifiedReport(tenantId, claimId, versionStamp, idempotencyKey),
    [tenantId, claimId, versionStamp],
  );

  const action = useGovernedAction({
    tenantId,
    objectId: claimId,
    objectType: 'claim',
    actionFingerprint: buildActionFingerprint(tenantId, 'claim', claimId, 'export_verified_report'),
    policyAuthority,
    consequence: 'external_artifact',
    permissionOk: hasActionPermission(getCurrentUserRole(), 'export_claim_report'),
    permissionDeniedCopy: ACTION_COPY.permissionDenied,
    subsystemSafe,
    subsystemCopy,
    onExecute,
  });

  const handleOpen = useCallback(() => {
    action.openConfirmation();
    if (action.phase === 'idle') setShowToast(false);
  }, [action]);

  const handleConfirm = useCallback(() => {
    action.confirm();
    setShowToast(true);
  }, [action]);

  return (
    <div className={styles.wrap} data-claim-export-flow>
      {preview ? (
        <div className={styles.preview} data-export-preview aria-label="Export preview">
          <h3>Verified report preview</h3>
          <ul className={styles.legend}>
            {preview.authorityLegend.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <p data-export-incrementality-copy>{preview.incrementalityBoundaryCopy}</p>
          <div className={styles.row}>
            <span>Platform claim</span>
            <AuthorityBadge authority="prior" label="Platform claim" />
            <span>{preview.claimedRevenueMinor} {preview.currencyCode} minor units</span>
          </div>
          <div className={styles.row}>
            <span>Verified revenue</span>
            <AuthorityBadge authority="deterministic" label="Verified revenue" />
            <span>{preview.verifiedRevenueMinor} {preview.currencyCode} minor units</span>
          </div>
          <p>{preview.confidenceSummary}</p>
          <p>{preview.benchmarkSummary}</p>
          <p>Audit reference: {preview.auditReference}</p>
        </div>
      ) : null}
      <GovernedActionControl
        actionLabel="Export verified report"
        policyAuthority={policyAuthority}
        disabled={action.disabled}
        disabledReason={action.disabledReason}
        phase={action.phase}
        outcome={action.outcome}
        confirmationTitle="Export verified report"
        confirmationBody={
          <>
            <p>This creates an externally shareable verified report. No new financial truth is created.</p>
            <p>{ACTION_COPY.incrementalityLegend}</p>
          </>
        }
        policyCopyInModal={`Policy authority: ${policyAuthority}`}
        triggerRef={triggerRef}
        onOpen={handleOpen}
        onConfirm={handleConfirm}
        onCancel={action.cancel}
        showToast={showToast && action.outcome !== null}
        onDismissToast={() => setShowToast(false)}
      />
    </div>
  );
}
