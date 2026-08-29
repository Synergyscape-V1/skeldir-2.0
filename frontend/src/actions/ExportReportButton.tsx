import { useEffect, useRef, useState } from 'react';
import { getAuthState } from '../auth/sessionStore';
import { getCurrentUserRole } from '../governance/governanceStore';
import { ACTION_COPY } from './copy';
import { exportArtifact } from './trustEnvelopeActionClient';
import { hasActionPermission } from './permissions';
import { checkSubsystemSafetyForExternalAction } from './systemSafety';
import { GovernedActionControl } from './GovernedActionControl';
import { useGovernedAction } from './useGovernedAction';
import { buildActionFingerprint } from './idempotency';
import type { PolicyAuthorityState } from '../lib/types';
import { IconDownload } from '../components/icons/StatusIcons';
import styles from './ExportReportButton.module.css';

export interface ExportReportButtonProps {
  envelopeId: string;
  versionStamp: string;
  policyAuthority: PolicyAuthorityState;
  triggerClassName?: string;
  layout?: 'inline' | 'header';
}

export function ExportReportButton({
  envelopeId,
  versionStamp,
  policyAuthority,
  triggerClassName,
  layout = 'inline',
}: ExportReportButtonProps) {
  const { tenant } = getAuthState();
  const tenantId = tenant?.tenantId ?? '';
  const [subsystemSafe, setSubsystemSafe] = useState(true);
  const [subsystemCopy, setSubsystemCopy] = useState<string>();
  const [showToast, setShowToast] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const actionFingerprint = buildActionFingerprint(
    tenantId,
    'trust_envelope',
    envelopeId,
    'export_artifact',
  );

  useEffect(() => {
    void checkSubsystemSafetyForExternalAction(tenantId, false, true).then((s) => {
      setSubsystemSafe(s.safe);
      setSubsystemCopy(s.copy);
    });
  }, [tenantId]);

  const action = useGovernedAction({
    tenantId,
    objectId: envelopeId,
    objectType: 'trust_envelope',
    actionFingerprint,
    policyAuthority,
    consequence: 'external_artifact',
    permissionOk: hasActionPermission(getCurrentUserRole(), 'export_trust_artifact'),
    permissionDeniedCopy: ACTION_COPY.permissionDenied,
    subsystemSafe,
    subsystemCopy,
    requiresConfirm: true,
    onExecute: (key) => exportArtifact(tenantId, envelopeId, versionStamp, key),
  });

  if (!tenant) return null;

  return (
    <div
      className={layout === 'header' ? styles.headerRow : styles.row}
      data-export-report-button
      data-trust-envelope-actions
    >
      <GovernedActionControl
        actionLabel="Export report"
        policyAuthority={policyAuthority}
        disabled={action.disabled}
        disabledReason={action.disabledReason}
        phase={action.phase}
        outcome={action.outcome}
        confirmationTitle="Export verified report"
        confirmationBody={
          <p>Exports a governed report for external review. Forensic verification stays in the Audit Ledger.</p>
        }
        destructive
        triggerRef={triggerRef}
        triggerClassName={triggerClassName ?? styles.primaryAction}
        leadingIcon={layout === 'header' ? <IconDownload className={styles.actionIcon} aria-hidden /> : undefined}
        align="end"
        outcomeVisibility="sr-only"
        showOutcomeDetails
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
    </div>
  );
}

/** @deprecated Use ExportReportButton */
export const TrustEnvelopeExportArtifactButton = ExportReportButton;
