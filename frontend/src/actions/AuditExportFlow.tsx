import { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { getAuthState } from '../auth/sessionStore';
import { getCurrentUserRole } from '../governance/governanceStore';
import { parseAuditFilters } from '../operationalAudit/parseAuditFilters';
import { ACTION_COPY } from './copy';
import { exportAuditReconstruction, getDefaultAuditExportClient } from './auditExportClient';
import { buildActionFingerprint } from './idempotency';
import { hasActionPermission } from './permissions';
import { checkSubsystemSafetyForExternalAction } from './systemSafety';
import { GovernedActionControl } from './GovernedActionControl';
import { useGovernedAction } from './useGovernedAction';
import type { AuditReconstructionPreview } from './types';
import type { PolicyAuthorityState } from '../lib/types';
import styles from './AuditExportFlow.module.css';

export interface AuditExportFlowProps {
  selectedEventId?: string | null;
  policyAuthority?: PolicyAuthorityState;
}

export function AuditExportFlow({ selectedEventId = null, policyAuthority = 'proposal_required' }: AuditExportFlowProps) {
  const location = useLocation();
  const filters = parseAuditFilters(location.search);
  const [preview, setPreview] = useState<AuditReconstructionPreview | null>(null);
  const [subsystemSafe, setSubsystemSafe] = useState(true);
  const [subsystemCopy, setSubsystemCopy] = useState<string>();
  const [showToast, setShowToast] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const { tenant } = getAuthState();
  const tenantId = tenant?.tenantId ?? '';

  useEffect(() => {
    void getDefaultAuditExportClient().buildReconstructionPreview(tenantId, filters).then(setPreview);
    void checkSubsystemSafetyForExternalAction(tenantId, true, true).then((s) => {
      setSubsystemSafe(s.safe);
      setSubsystemCopy(s.copy);
    });
  }, [tenantId, location.search]);

  const onExecute = useCallback(
    (idempotencyKey: string) =>
      exportAuditReconstruction(tenantId, filters, selectedEventId, idempotencyKey),
    [tenantId, filters, selectedEventId],
  );

  const auditObjectId = selectedEventId ?? `filters:${location.search}`;

  const action = useGovernedAction({
    tenantId,
    objectId: auditObjectId,
    objectType: 'audit_event',
    actionFingerprint: buildActionFingerprint(tenantId, 'audit_event', auditObjectId, 'export_reconstruction'),
    policyAuthority,
    consequence: 'external_artifact',
    permissionOk: hasActionPermission(getCurrentUserRole(), 'export_audit_reconstruction'),
    permissionDeniedCopy: ACTION_COPY.permissionDenied,
    subsystemSafe,
    subsystemCopy,
    onExecute,
  });

  return (
    <div data-audit-export-flow className={styles.wrap}>
      {preview ? (
        <div className={styles.preview} data-audit-reconstruction-preview>
          <h3>Reconstruction preview</h3>
          <p>Events: {preview.eventIds.length}</p>
          <p>Hash chain: {preview.hashChain.join(' → ')}</p>
          <ul>
            {preview.redactionSummary.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>
      ) : null}
      <GovernedActionControl
        actionLabel="Export audit reconstruction"
        policyAuthority={policyAuthority}
        disabled={action.disabled}
        disabledReason={action.disabledReason}
        phase={action.phase}
        outcome={action.outcome}
        confirmationTitle="Export audit reconstruction"
        confirmationBody={<p>Redacted export for reconstruction support. Not a source-of-truth replacement.</p>}
        triggerRef={triggerRef}
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
