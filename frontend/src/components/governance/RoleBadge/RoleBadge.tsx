import { GOVERNANCE_COPY } from '../../../governance/copy';
import type { TeamRole } from '../../../governance/types';
import { TEAM_ROLES } from '../../../governance/types';
import { TrustChip, type TrustChipTone } from '../../trust/TrustChip/TrustChip';
import shared from '../../../styles/shared.module.css';
import styles from './RoleBadge.module.css';

export interface RoleBadgeProps {
  role: TeamRole | string;
}

const ROLE_TONE: Record<TeamRole, TrustChipTone> = {
  owner: 'info',
  admin: 'probabilistic',
  manager: 'neutral',
  viewer: 'neutral',
  billing_only: 'neutral',
  unknown_role: 'error',
};

const ROLE_TABLE_LABEL: Record<TeamRole, string> = {
  owner: 'owner',
  admin: 'admin',
  manager: 'manager',
  viewer: 'viewer',
  billing_only: 'billing',
  unknown_role: 'unknown',
};

export function RoleBadge({ role }: RoleBadgeProps) {
  if (!TEAM_ROLES.includes(role as TeamRole) || role === 'unknown_role') {
    return (
      <TrustChip tone="error" role="alert" title={GOVERNANCE_COPY.unknownRoleError}>
        unknown
      </TrustChip>
    );
  }

  const resolved = role as TeamRole;
  return (
    <TrustChip tone={ROLE_TONE[resolved]} title={GOVERNANCE_COPY.roleLabels[resolved]}>
      {ROLE_TABLE_LABEL[resolved]}
    </TrustChip>
  );
}

export interface RoleChangeControlProps {
  memberId: string;
  currentRole: TeamRole | string;
  disabled?: boolean;
  pending?: boolean;
  onChange: (memberId: string, role: TeamRole) => void;
}

const CHANGEABLE_ROLES: TeamRole[] = ['admin', 'manager', 'viewer'];

export function RoleChangeControl({
  memberId,
  currentRole,
  disabled,
  pending,
  onChange,
}: RoleChangeControlProps) {
  if (!TEAM_ROLES.includes(currentRole as TeamRole) || currentRole === 'unknown_role') {
    return <RoleBadge role={currentRole} />;
  }

  return (
    <label className={styles.control}>
      <span className="sr-only">Change role for member {memberId}</span>
      <select
        className={[styles.select, shared.focusVisible].join(' ')}
        value={currentRole}
        disabled={disabled || pending}
        aria-busy={pending}
        onChange={(e) => onChange(memberId, e.target.value as TeamRole)}
      >
        {CHANGEABLE_ROLES.map((role) => (
          <option key={role} value={role}>
            {GOVERNANCE_COPY.roleLabels[role]}
          </option>
        ))}
      </select>
    </label>
  );
}
