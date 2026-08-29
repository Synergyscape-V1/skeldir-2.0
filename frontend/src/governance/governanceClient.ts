import type { PolicyAuthorityState } from '../lib/types';
import type {
  AgentCredential,
  AgentKeyCreateInput,
  AgentKeyCreateOutcome,
  AgentListOutcome,
  AgentScope,
  GovernanceTransport,
  PolicyActionCategory,
  PolicyOutcome,
  PolicySettings,
  TeamMember,
  TeamOutcome,
  TeamRole,
  AutoExecuteConstraints,
} from './types';
import {
  ALLOWED_AGENT_SCOPES,
  POLICY_ACTION_CATEGORIES,
} from './types';
import { GOVERNANCE_COPY } from './copy';
import { canManageTeam, canCreateAgentKey, canConfigurePolicy, canRevokeAgent } from './permissions';

let defaultClient: ReturnType<typeof createGovernanceClient> | null = null;

export interface GovernanceClient {
  getTeam(tenantId: string, signal?: AbortSignal): Promise<TeamOutcome>;
  changeMemberRole(
    tenantId: string,
    memberId: string,
    role: TeamRole,
    signal?: AbortSignal,
  ): Promise<TeamOutcome>;
  removeMember(tenantId: string, memberId: string, signal?: AbortSignal): Promise<TeamOutcome>;
  listAgents(tenantId: string, signal?: AbortSignal): Promise<AgentListOutcome>;
  createAgentKey(
    tenantId: string,
    input: AgentKeyCreateInput,
    signal?: AbortSignal,
  ): Promise<AgentKeyCreateOutcome>;
  revokeAgent(tenantId: string, agentId: string, signal?: AbortSignal): Promise<AgentListOutcome>;
  getPolicy(tenantId: string, signal?: AbortSignal): Promise<PolicyOutcome>;
  savePolicyCategory(
    tenantId: string,
    category: PolicyActionCategory,
    authority: PolicyAuthorityState,
    constraints?: AutoExecuteConstraints,
    signal?: AbortSignal,
  ): Promise<PolicyOutcome>;
}

export function createGovernanceClient(transport: GovernanceTransport): GovernanceClient {
  return {
    getTeam: (tenantId, signal) => transport.getTeam(tenantId, signal),
    changeMemberRole: (tenantId, memberId, role, signal) =>
      transport.changeMemberRole(tenantId, memberId, role, signal),
    removeMember: (tenantId, memberId, signal) =>
      transport.removeMember(tenantId, memberId, signal),
    listAgents: (tenantId, signal) => transport.listAgents(tenantId, signal),
    createAgentKey: (tenantId, input, signal) =>
      transport.createAgentKey(tenantId, input, signal),
    revokeAgent: (tenantId, agentId, signal) =>
      transport.revokeAgent(tenantId, agentId, signal),
    getPolicy: (tenantId, signal) => transport.getPolicy(tenantId, signal),
    savePolicyCategory: (tenantId, category, authority, constraints, signal) =>
      transport.savePolicyCategory(tenantId, category, authority, constraints, signal),
  };
}

function defaultTeamMembers(): TeamMember[] {
  return [
    {
      memberId: 'mem_001',
      displayLabel: 'Operator A.',
      role: 'owner',
      status: 'active',
      lastActiveAt: new Date().toISOString(),
      isCurrentUser: true,
    },
    {
      memberId: 'mem_002',
      displayLabel: 'Strategist B.',
      role: 'manager',
      status: 'active',
      lastActiveAt: new Date(Date.now() - 86400_000).toISOString(),
    },
    {
      memberId: 'mem_003',
      displayLabel: 'Viewer C.',
      role: 'viewer',
      status: 'active',
      lastActiveAt: undefined,
    },
  ];
}

function defaultAgents(): AgentCredential[] {
  return [
    {
      agentId: 'agt_001',
      name: 'Finance read agent',
      description: 'Read-only trust envelope consumer',
      scopes: ['trust:read', 'artifact:read'],
      createdAt: new Date(Date.now() - 7 * 86400_000).toISOString(),
      expiresAt: new Date(Date.now() + 90 * 86400_000).toISOString(),
      status: 'active',
      lastUsedAt: new Date(Date.now() - 3600_000).toISOString(),
      rateLimitPerMinute: 60,
      allowedIpsSummary: 'Any',
    },
  ];
}

function defaultPolicy(): PolicySettings {
  return {
    mode: 'design_partner',
    modeLabel: 'Design Partner Mode',
    categories: POLICY_ACTION_CATEGORIES.map((category) => ({
      category,
      authority: category === 'budget_simulation' ? 'simulation_only' : 'blocked',
    })),
  };
}

export interface MockGovernanceOptions {
  currentUserRole?: TeamRole;
  members?: TeamMember[];
  agents?: AgentCredential[];
  policy?: PolicySettings;
  delayMs?: number;
  denyPermissions?: boolean;
}

function delay(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener('abort', () => {
      clearTimeout(timer);
      reject(new DOMException('Aborted', 'AbortError'));
    });
  });
}

export function createMockGovernanceTransport(
  options: MockGovernanceOptions = {},
): GovernanceTransport {
  let members = options.members ?? defaultTeamMembers();
  let agents = options.agents ?? defaultAgents();
  let policy = options.policy ?? defaultPolicy();
  const currentRole = options.currentUserRole ?? 'owner';

  return {
    async getTeam(_tenantId, signal) {
      if (options.delayMs) await delay(options.delayMs, signal);
      return { kind: 'team_loaded', members, currentUserRole: currentRole };
    },
    async changeMemberRole(_tenantId, memberId, role, signal) {
      if (options.delayMs) await delay(options.delayMs, signal);
      if (options.denyPermissions || !canManageTeam(currentRole)) {
        return { kind: 'permission_denied', message: GOVERNANCE_COPY.permissionDeniedBody };
      }
      members = members.map((m) => (m.memberId === memberId ? { ...m, role } : m));
      return { kind: 'role_changed', memberId, newRole: role };
    },
    async removeMember(_tenantId, memberId, signal) {
      if (options.delayMs) await delay(options.delayMs, signal);
      if (options.denyPermissions || !canManageTeam(currentRole)) {
        return { kind: 'permission_denied', message: GOVERNANCE_COPY.permissionDeniedBody };
      }
      members = members.filter((m) => m.memberId !== memberId);
      return { kind: 'member_removed', memberId };
    },
    async listAgents(_tenantId, signal) {
      if (options.delayMs) await delay(options.delayMs, signal);
      if (currentRole === 'unknown_role') {
        return { kind: 'permission_denied', message: GOVERNANCE_COPY.permissionDeniedBody };
      }
      return { kind: 'agents_loaded', agents };
    },
    async createAgentKey(_tenantId, input, signal) {
      if (options.delayMs) await delay(options.delayMs, signal);
      if (!canCreateAgentKey(currentRole)) {
        return { kind: 'permission_denied', message: GOVERNANCE_COPY.permissionDeniedBody };
      }
      if (!input.name.trim()) {
        return { kind: 'validation_error', message: GOVERNANCE_COPY.validation.nameRequired };
      }
      if (!input.readOnlyAcknowledged) {
        return {
          kind: 'validation_error',
          message: GOVERNANCE_COPY.validation.acknowledgementRequired,
        };
      }
      if (!input.scopes.length || !input.scopes.every((s) => ALLOWED_AGENT_SCOPES.includes(s))) {
        return { kind: 'validation_error', message: GOVERNANCE_COPY.validation.scopesRequired };
      }
      if (input.expirationDays < 1 || input.expirationDays > 365) {
        return { kind: 'validation_error', message: GOVERNANCE_COPY.validation.expirationInvalid };
      }
      if (input.rateLimitPerMinute < 1 || input.rateLimitPerMinute > 1000) {
        return { kind: 'validation_error', message: GOVERNANCE_COPY.validation.rateLimitInvalid };
      }
      const agent: AgentCredential = {
        agentId: `agt_${Date.now()}`,
        name: input.name,
        description: input.description,
        scopes: input.scopes,
        createdAt: new Date().toISOString(),
        expiresAt: new Date(Date.now() + input.expirationDays * 86400_000).toISOString(),
        status: 'active',
        rateLimitPerMinute: input.rateLimitPerMinute,
        allowedIpsSummary: input.allowedIps?.length ? input.allowedIps.join(', ') : 'Any',
      };
      agents = [...agents, agent];
      return {
        kind: 'agent_created',
        agent,
        secretPlaceholder: GOVERNANCE_COPY.agentSecretPlaceholder,
      };
    },
    async revokeAgent(_tenantId, agentId, signal) {
      if (options.delayMs) await delay(options.delayMs, signal);
      if (!canRevokeAgent(currentRole)) {
        return { kind: 'permission_denied', message: GOVERNANCE_COPY.permissionDeniedBody };
      }
      agents = agents.map((a) =>
        a.agentId === agentId ? { ...a, status: 'revoked' as const } : a,
      );
      return { kind: 'agent_revoked', agentId };
    },
    async getPolicy(_tenantId, signal) {
      if (options.delayMs) await delay(options.delayMs, signal);
      if (!canConfigurePolicy(currentRole) && currentRole === 'unknown_role') {
        return { kind: 'permission_denied', message: GOVERNANCE_COPY.permissionDeniedBody };
      }
      return { kind: 'policy_loaded', policy };
    },
    async savePolicyCategory(_tenantId, category, authority, constraints, signal) {
      if (options.delayMs) await delay(options.delayMs, signal);
      if (!canConfigurePolicy(currentRole)) {
        return { kind: 'permission_denied', message: GOVERNANCE_COPY.permissionDeniedBody };
      }
      if (
        authority === 'auto_executable_within_policy' &&
        policy.mode === 'design_partner'
      ) {
        return { kind: 'validation_error', message: 'Invalid authority state returned.' };
      }
      if (authority === 'auto_executable_within_policy' && !constraints) {
        return { kind: 'validation_error', message: 'Auto-execute constraints required.' };
      }
      policy = {
        ...policy,
        categories: policy.categories.map((c) =>
          c.category === category
            ? { category, authority, autoExecuteConstraints: constraints }
            : c,
        ),
      };
      return { kind: 'policy_saved', policy };
    },
  };
}

export function setDefaultGovernanceClient(client: GovernanceClient): void {
  defaultClient = client;
}

export function getDefaultGovernanceClient(): GovernanceClient {
  if (!defaultClient) {
    defaultClient = createGovernanceClient(createMockGovernanceTransport());
  }
  return defaultClient;
}

export function resetDefaultGovernanceClient(): void {
  defaultClient = null;
}

export function validateAgentScopes(scopes: AgentScope[]): boolean {
  return scopes.length > 0 && scopes.every((s) => ALLOWED_AGENT_SCOPES.includes(s));
}

export function validateAllowedIps(value: string): boolean {
  if (!value.trim()) return true;
  const parts = value.split(',').map((p) => p.trim());
  return parts.every((ip) => /^(\d{1,3}\.){3}\d{1,3}$/.test(ip));
}
