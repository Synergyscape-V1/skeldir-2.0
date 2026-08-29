import { Table, type TableColumn } from '../../layout/Table/Table';
import { GOVERNANCE_COPY } from '../../../governance/copy';
import type { TeamMember } from '../../../governance/types';
import { RoleBadge, RoleChangeControl } from '../RoleBadge/RoleBadge';
import { MemberStatusBadge } from '../MemberStatusBadge/MemberStatusBadge';
import { ERROR_COPY, LOADING_COPY } from '../../../lib/copy';
import { useTimedTableLoading } from '../../../lib/loading';
import styles from './TeamMembersTable.module.css';

export interface TeamMembersTableProps {
  members: TeamMember[];
  loading?: boolean;
  error?: string;
  permissionDenied?: boolean;
  canManage?: boolean;
  roleChangePending?: string;
  roleChangeDenied?: string;
  onRoleChange?: (memberId: string, role: import('../../../governance/types').TeamRole) => void;
  onRetry?: () => void;
}

export function TeamMembersTable({
  members,
  loading,
  error,
  permissionDenied,
  canManage,
  roleChangePending,
  roleChangeDenied,
  onRoleChange,
  onRetry,
}: TeamMembersTableProps) {
  const timedLoading = useTimedTableLoading(!!loading, {
    progressCopy: LOADING_COPY.progress,
    onRetry,
  });

  if (permissionDenied) {
    return (
      <Table
        caption={GOVERNANCE_COPY.teamTableCaption}
        columns={[]}
        rows={[]}
        state="permission_denied"
        getRowKey={() => ''}
      />
    );
  }

  if (timedLoading) {
    return (
      <Table
        caption={GOVERNANCE_COPY.teamTableCaption}
        columns={[]}
        rows={[]}
        state={timedLoading.state}
        progressCopy={timedLoading.progressCopy}
        onRetry={timedLoading.onRetry}
        getRowKey={() => ''}
      />
    );
  }

  if (error) {
    return (
      <Table
        caption={GOVERNANCE_COPY.teamTableCaption}
        columns={[]}
        rows={[]}
        state="error"
        errorMessage={error}
        getRowKey={() => ''}
      />
    );
  }

  if (!members.length) {
    return (
      <Table
        caption={GOVERNANCE_COPY.teamTableCaption}
        columns={[]}
        rows={[]}
        state="empty"
        emptyTitle="No team members"
        emptyDescription="This workspace has no members yet."
        getRowKey={() => ''}
      />
    );
  }

  const columns: TableColumn<TeamMember>[] = [
    {
      key: 'label',
      header: 'Member',
      render: (row) => (
        <span>
          {row.displayLabel}
          {row.isCurrentUser ? <span className={styles.you}> (you)</span> : null}
        </span>
      ),
    },
    {
      key: 'role',
      header: 'Role',
      render: (row) =>
        canManage && !row.isCurrentUser && row.role !== 'owner' && onRoleChange ? (
          <div>
            <RoleChangeControl
              memberId={row.memberId}
              currentRole={row.role}
              disabled={!canManage}
              pending={roleChangePending === row.memberId}
              onChange={onRoleChange}
            />
            {roleChangeDenied === row.memberId ? (
              <span className={styles.denied} role="alert">
                {ERROR_COPY.permissionDenied}
              </span>
            ) : null}
          </div>
        ) : (
          <RoleBadge role={row.role} />
        ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (row) => <MemberStatusBadge status={row.status} />,
    },
    {
      key: 'lastActive',
      header: 'Last active',
      render: (row) =>
        row.lastActiveAt
          ? new Date(row.lastActiveAt).toLocaleDateString()
          : 'Unavailable',
    },
  ];

  return (
    <Table
      caption={GOVERNANCE_COPY.teamTableCaption}
      columns={columns}
      rows={members}
      state="populated"
      getRowKey={(row) => row.memberId}
    />
  );
}
