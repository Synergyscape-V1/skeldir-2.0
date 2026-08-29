import { useCallback, useEffect, useRef, useState } from 'react';
import { getAuthState } from '../auth/sessionStore';
import { getCurrentUserRole } from '../governance/governanceStore';
import type { ClaimsFilters } from '../claims/claimsClient';
import { CLAIMS_LEDGER_PAGE_COPY } from '../claims/copy';
import { IconDownload } from '../components/icons/StatusIcons';
import { ACTION_COPY } from './copy';
import {
  exportVerifiedLedgerReport,
  getDefaultClaimsLedgerExportClient,
} from './claimsLedgerExportClient';
import { buildActionFingerprint } from './idempotency';
import { hasActionPermission } from './permissions';
import { checkSubsystemSafetyForExternalAction } from './systemSafety';
import { GovernedActionControl } from './GovernedActionControl';
import { useGovernedAction } from './useGovernedAction';
import type { ClaimsLedgerExportPreview } from './types';
import type { PolicyAuthorityState } from '../lib/types';
import styles from './ClaimsLedgerExportFlow.module.css';

export interface ClaimsLedgerExportFlowProps {
  filters: ClaimsFilters;
  policyAuthority?: PolicyAuthorityState;
  layout?: 'header' | 'panel';
}

export function ClaimsLedgerExportFlow({
  filters,
  policyAuthority = 'proposal_required',
  layout = 'header',
}: ClaimsLedgerExportFlowProps) {
  const [preview, setPreview] = useState<ClaimsLedgerExportPreview | null>(null);
  const [subsystemSafe, setSubsystemSafe] = useState(true);
  const [subsystemCopy, setSubsystemCopy] = useState<string>();
  const [showToast, setShowToast] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const { tenant } = getAuthState();
  const tenantId = tenant?.tenantId ?? '';
  const filterKey = JSON.stringify(filters);

  useEffect(() => {
    void getDefaultClaimsLedgerExportClient().buildLedgerExportPreview(tenantId, filters).then(setPreview);
    void checkSubsystemSafetyForExternalAction(tenantId, false, true).then((s) => {
      setSubsystemSafe(s.safe);
      setSubsystemCopy(s.copy);
    });
  }, [tenantId, filterKey, filters]);

  const objectId = `ledger:${filterKey}`;

  const onExecute = useCallback(
    (idempotencyKey: string) => exportVerifiedLedgerReport(tenantId, filters, idempotencyKey),
    [tenantId, filters],
  );

  const action = useGovernedAction({
    tenantId,
    objectId,
    objectType: 'claim',
    actionFingerprint: buildActionFingerprint(tenantId, 'claim', objectId, 'export_verified_ledger_report'),
    policyAuthority,
    consequence: 'external_artifact',
    permissionOk: hasActionPermission(getCurrentUserRole(), 'export_claim_report'),
    permissionDeniedCopy: ACTION_COPY.permissionDenied,
    subsystemSafe,
    subsystemCopy,
    onExecute,
  });

  const showPanelPreview = layout === 'panel' && preview;

  return (
    <div
      data-claims-ledger-export-flow
      data-claims-ledger-export-layout={layout}
      className={layout === 'header' ? styles.headerWrap : styles.panelWrap}
    >
      {showPanelPreview ? (
        <div className={styles.preview} data-claims-ledger-export-preview>
          <h3>Verified ledger report preview</h3>
          <p>Claims in scope: {preview.totalCount}</p>
          <ul>
            {preview.filterSummary.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>
      ) : null}
      <GovernedActionControl
        actionLabel={CLAIMS_LEDGER_PAGE_COPY.exportAction}
        policyAuthority={policyAuthority}
        disabled={action.disabled}
        disabledReason={action.disabledReason}
        phase={action.phase}
        outcome={action.outcome}
        confirmationTitle={CLAIMS_LEDGER_PAGE_COPY.exportAction}
        confirmationBody={
          <>
            <p>{CLAIMS_LEDGER_PAGE_COPY.exportConfirmation}</p>
            <p>{ACTION_COPY.incrementalityLegend}</p>
            {preview ? <p>Claims in scope: {preview.totalCount}</p> : null}
          </>
        }
        policyCopyInModal={`Policy authority: ${policyAuthority}`}
        triggerRef={triggerRef}
        triggerClassName={layout === 'header' ? styles.headerButton : undefined}
        leadingIcon={layout === 'header' ? <IconDownload aria-hidden /> : undefined}
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
