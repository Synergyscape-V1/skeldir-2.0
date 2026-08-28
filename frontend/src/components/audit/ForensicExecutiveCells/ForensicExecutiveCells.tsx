import type { HTMLAttributes, ReactNode } from 'react';
import { PolicyAuthorityPill } from '../../trust/PolicyAuthorityPill/PolicyAuthorityPill';
import { COMMAND_CENTER_CHIP_PROPS } from '../../../commandCenter/commandCenterChipProps';
import { resolveForensicExecutiveStatus } from '../../../operationalAudit/forensicExecutiveDisplay';
import type { AuditEvent, ForensicChainVerification } from '../../../operationalAudit/types';
import statusText from '../../../styles/trustStatusText.module.css';

function ForensicExecutiveText({
  className,
  children,
  ...rest
}: { className: string; children: ReactNode } & HTMLAttributes<HTMLSpanElement>) {
  return (
    <span className={className} data-status-text role="status" {...rest}>
      {children}
    </span>
  );
}

export function ForensicExecutiveStatusCell({ row }: { row: AuditEvent }) {
  const status = resolveForensicExecutiveStatus(row);

  if (status.kind === 'exported') {
    return (
      <ForensicExecutiveText className={statusText.labelSuccess} data-forensic-executive-status="exported">
        Exported
      </ForensicExecutiveText>
    );
  }

  if (status.kind === 'proposal_generated') {
    return (
      <ForensicExecutiveText className={statusText.labelInfo} data-forensic-executive-status="proposal_generated">
        Proposal generated
      </ForensicExecutiveText>
    );
  }

  return (
    <PolicyAuthorityPill
      state={status.state}
      {...COMMAND_CENTER_CHIP_PROPS}
      appearance="text"
    />
  );
}

export function ForensicChainVerificationBadge({ status }: { status: ForensicChainVerification }) {
  const intact = status === 'intact';
  return (
    <ForensicExecutiveText
      className={intact ? statusText.labelSuccess : statusText.labelWarning}
      data-forensic-chain-verification={status}
    >
      {intact ? 'Chain Intact' : 'Review Required'}
    </ForensicExecutiveText>
  );
}