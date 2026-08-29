import type { PolicyAuthorityState, TenantPolicyMode } from '../lib/types';

export type TeamRole = 'owner' | 'admin' | 'manager' | 'viewer' | 'billing_only' | 'unknown_role';

export const TEAM_ROLES: readonly TeamRole[] = [
  'owner',
  'admin',
  'manager',
  'viewer',
  'billing_only',
  'unknown_role',
];

export type MemberStatus = 'active' | 'invited' | 'suspended' | 'removed';

export interface TeamMember {
  memberId: string;
  displayLabel: string;
  role: TeamRole;
  status: MemberStatus;
  lastActiveAt?: string;
  isCurrentUser?: boolean;
}

export type AgentScope =
  | 'trust:read'
  | 'claim:verify'
  | 'artifact:read'
  | 'audit:read'
  | 'propose_action'
  | 'execute_action'
  | 'refit_bayesian'
  | 'resolve_exception';

export const ALLOWED_AGENT_SCOPES: readonly AgentScope[] = [
  'trust:read',
  'claim:verify',
  'artifact:read',
  'audit:read',
];

export const RESERVED_AGENT_SCOPES: readonly AgentScope[] = [
  'propose_action',
  'execute_action',
  'refit_bayesian',
  'resolve_exception',
];

export const ALL_AGENT_SCOPES: readonly AgentScope[] = [
  ...ALLOWED_AGENT_SCOPES,
  ...RESERVED_AGENT_SCOPES,
];

export type AgentCredentialStatus = 'active' | 'expired' | 'revoked';

export interface AgentCredential {
  agentId: string;
  name: string;
  description: string;
  scopes: AgentScope[];
  createdAt: string;
  expiresAt: string;
  status: AgentCredentialStatus;
  lastUsedAt?: string;
  rateLimitPerMinute: number;
  allowedIpsSummary: string;
}

export type PolicyActionCategory =
  | 'revenue_reads'
  | 'attribution_reads'
  | 'confidence_reads'
  | 'budget_simulation'
  | 'budget_proposal'
  | 'budget_execution'
  | 'external_export'
  | 'agent_api_access';

export const POLICY_ACTION_CATEGORIES: readonly PolicyActionCategory[] = [
  'revenue_reads',
  'attribution_reads',
  'confidence_reads',
  'budget_simulation',
  'budget_proposal',
  'budget_execution',
  'external_export',
  'agent_api_access',
];

export interface AutoExecuteConstraints {
  budgetCeilingMinor: number;
  cooldownPeriodHours: number;
  hysteresisThresholdPercent: number;
}

export interface PolicyCategoryConfig {
  category: PolicyActionCategory;
  authority: PolicyAuthorityState;
  autoExecuteConstraints?: AutoExecuteConstraints;
}

export interface PolicySettings {
  mode: TenantPolicyMode;
  modeLabel: string;
  categories: PolicyCategoryConfig[];
}

export type GovernanceErrorKind =
  | 'permission_denied'
  | 'network_failure'
  | 'rate_limited'
  | 'validation_error'
  | 'not_found'
  | 'unknown';

export interface GovernanceError {
  kind: GovernanceErrorKind;
  message: string;
}

export type TeamOutcome =
  | { kind: 'team_loaded'; members: TeamMember[]; currentUserRole: TeamRole }
  | { kind: 'role_changed'; memberId: string; newRole: TeamRole }
  | { kind: 'member_removed'; memberId: string }
  | { kind: 'invite_pending' }
  | GovernanceError;

export type AgentListOutcome =
  | { kind: 'agents_loaded'; agents: AgentCredential[] }
  | { kind: 'agent_revoked'; agentId: string }
  | GovernanceError;

export interface AgentKeyCreateInput {
  name: string;
  description: string;
  expirationDays: number;
  scopes: AgentScope[];
  rateLimitPerMinute: number;
  allowedIps?: string[];
  readOnlyAcknowledged: boolean;
}

export type AgentKeyCreateOutcome =
  | { kind: 'agent_created'; agent: AgentCredential; secretPlaceholder: string }
  | GovernanceError;

export type PolicyOutcome =
  | { kind: 'policy_loaded'; policy: PolicySettings }
  | { kind: 'policy_saved'; policy: PolicySettings }
  | GovernanceError;

export interface GovernanceTransport {
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
