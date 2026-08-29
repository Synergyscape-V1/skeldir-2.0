import { GOVERNANCE_COPY } from '../../../governance/copy';
import type { MemberStatus } from '../../../governance/types';
import { TrustChip, type TrustChipTone } from '../../trust/TrustChip/TrustChip';
import styles from './MemberStatusBadge.module.css';

export interface MemberStatusBadgeProps {
  status: MemberStatus;
}

const STATUS_TONE: Record<MemberStatus, TrustChipTone> = {
  active: 'success',
  invited: 'info',
  suspended: 'neutral',
  removed: 'neutral',
};

const STATUS_TABLE_LABEL: Record<MemberStatus, string> = {
  active: 'active',
  invited: 'invited',
  suspended: 'suspended',
  removed: 'removed',
};

export function MemberStatusBadge({ status }: MemberStatusBadgeProps) {
  return (
    <TrustChip tone={STATUS_TONE[status]} title={GOVERNANCE_COPY.memberStatusLabels[status]}>
      {STATUS_TABLE_LABEL[status]}
    </TrustChip>
  );
}

export function InviteMemberPlaceholder() {
  return (
    <p className={styles.invite} role="status" data-invite-placeholder>
      {GOVERNANCE_COPY.inviteNotAvailable}
    </p>
  );
}
