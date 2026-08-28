import { statusLabel } from '../../../integration/copy';
import type { IntegrationStatus } from '../../../integration/types';
import { TrustChip, type TrustChipTone } from '../../trust/TrustChip/TrustChip';

export interface IntegrationStatusBadgeProps {
  status: IntegrationStatus;
  id?: string;
}

function statusTone(status: IntegrationStatus): TrustChipTone {
  switch (status) {
    case 'connected':
    case 'verification_ready':
      return 'success';
    case 'connecting':
    case 'verification_pending':
    case 'repair_pending':
      return 'info';
    case 'repair_required':
    case 'connection_failed':
    case 'verification_failed':
    case 'permission_denied':
    case 'unknown_status':
      return 'error';
    case 'rate_limited':
    case 'last_event_unavailable':
    case 'last_claim_unavailable':
      return 'warning';
    default:
      return 'neutral';
  }
}

function tableLabel(status: IntegrationStatus): string {
  if (status === 'unknown_status') return 'Unknown';
  if (status === 'verification_ready') return 'Verified';
  if (status === 'verification_pending') return 'Verifying';
  if (status === 'repair_required') return 'Repair';
  if (status === 'connection_failed') return 'Failed';
  if (status === 'verification_failed') return 'Verify failed';
  if (status === 'permission_denied') return 'Denied';
  if (status === 'rate_limited') return 'Rate limited';
  if (status === 'last_event_unavailable') return 'No events';
  if (status === 'last_claim_unavailable') return 'No claims';
  if (status === 'repair_pending') return 'Repairing';
  return status.replace(/_/g, ' ').replace(/^\w/, (char) => char.toUpperCase());
}

export function IntegrationStatusBadge({ status, id }: IntegrationStatusBadgeProps) {
  const tone = statusTone(status);
  const fullLabel = status === 'unknown_status' ? 'Unknown status' : statusLabel(status);
  const label = tableLabel(status);

  return (
    <TrustChip
      id={id}
      tone={tone}
      data-integration-status={status}
      title={fullLabel}
      aria-label={fullLabel}
    >
      {label}
    </TrustChip>
  );
}
