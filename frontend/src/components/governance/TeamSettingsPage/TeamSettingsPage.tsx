import { PageSurface } from '../../layout/PageSurface/PageSurface';
import { Typography } from '../../layout/Typography/Typography';
import { GOVERNANCE_COPY } from '../../../governance/copy';
import { useTeamSettings } from '../../../governance/useTeamSettings';
import { SettingsSubnav } from '../../../app/routes/GovernanceRoutes';
import { PermissionDeniedPanel } from '../PermissionDeniedPanel/PermissionDeniedPanel';
import { TeamMembersTable } from '../TeamMembersTable/TeamMembersTable';
import { InviteMemberPlaceholder } from '../MemberStatusBadge/MemberStatusBadge';
import { RoleBadge } from '../RoleBadge/RoleBadge';
import styles from './TeamSettingsPage.module.css';

export function TeamSettingsPage() {
  const {
    members,
    currentUserRole,
    loading,
    error,
    permissionDenied,
    roleChangePending,
    roleChangeDenied,
    canManage,
    changeRole,
    refresh,
  } = useTeamSettings();

  if (permissionDenied) {
    return (
      <PageSurface>
        <PermissionDeniedPanel />
      </PageSurface>
    );
  }

  return (
    <PageSurface data-team-settings-page>
      <SettingsSubnav />
      <header className={styles.header}>
        <Typography variant="h2">{GOVERNANCE_COPY.teamPageTitle}</Typography>
        <p className={styles.description}>{GOVERNANCE_COPY.teamPageDescription}</p>
        <div className={styles.currentRole}>
          <span>Your role:</span>
          <RoleBadge role={currentUserRole} />
        </div>
      </header>
      <TeamMembersTable
        members={members}
        loading={loading}
        error={error}
        permissionDenied={permissionDenied}
        canManage={canManage}
        roleChangePending={roleChangePending}
        roleChangeDenied={roleChangeDenied}
        onRoleChange={changeRole}
        onRetry={() => void refresh()}
      />
      {canManage ? <InviteMemberPlaceholder /> : null}
    </PageSurface>
  );
}
