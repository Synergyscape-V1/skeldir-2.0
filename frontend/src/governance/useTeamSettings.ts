import { useCallback, useEffect, useState } from 'react';
import { getAuthState } from '../auth/sessionStore';
import { getDefaultGovernanceClient } from './governanceClient';
import { isGovernanceError, mapGovernanceError } from './governanceOutcomeMapping';
import { canManageTeam } from './permissions';
import type { TeamMember, TeamRole } from './types';
import { setCurrentUserRole } from './governanceStore';

export function useTeamSettings() {
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [currentUserRole, setRole] = useState<TeamRole>('owner');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | undefined>();
  const [permissionDenied, setPermissionDenied] = useState(false);
  const [roleChangePending, setRoleChangePending] = useState<string | undefined>();
  const [roleChangeDenied, setRoleChangeDenied] = useState<string | undefined>();

  const refresh = useCallback(async () => {
    const { tenant } = getAuthState();
    if (!tenant) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(undefined);
    setPermissionDenied(false);
    try {
      const client = getDefaultGovernanceClient();
      const outcome = await client.getTeam(tenant.tenantId);
      if (isGovernanceError(outcome)) {
        if (outcome.kind === 'permission_denied') setPermissionDenied(true);
        setError(mapGovernanceError(outcome));
        return;
      }
      if (outcome.kind === 'team_loaded') {
        setMembers(outcome.members);
        setRole(outcome.currentUserRole);
        setCurrentUserRole(outcome.currentUserRole);
      }
    } catch {
      setError('Team service unavailable. Try again shortly.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const changeRole = useCallback(
    async (memberId: string, role: TeamRole) => {
      if (!canManageTeam(currentUserRole)) {
        setRoleChangeDenied(memberId);
        return;
      }
      const { tenant } = getAuthState();
      if (!tenant) return;
      setRoleChangePending(memberId);
      setRoleChangeDenied(undefined);
      const client = getDefaultGovernanceClient();
      const outcome = await client.changeMemberRole(tenant.tenantId, memberId, role);
      setRoleChangePending(undefined);
      if (isGovernanceError(outcome)) {
        setRoleChangeDenied(memberId);
        setError(mapGovernanceError(outcome));
        return;
      }
      await refresh();
    },
    [currentUserRole, refresh],
  );

  return {
    members,
    currentUserRole,
    loading,
    error,
    permissionDenied,
    roleChangePending,
    roleChangeDenied,
    canManage: canManageTeam(currentUserRole),
    refresh,
    changeRole,
  };
}
