import type { SystemHealthState } from '../operationalAudit/types';
import { COMMAND_CENTER_COPY } from './copy';
import { COMMAND_CENTER_PRIORITY_ISSUES } from './commandCenterPriorityFixtures';
import { sortPriorityIssues } from './prioritySeverity';
import type { CommandCenterTestMode } from './types';
import type { PriorityIssue } from './types';

export const SUPERVISORY_PROJECTION_SOURCE = 'supervisory_projection';

export type SupervisoryProjectionOutcome =
  | { kind: 'loaded'; issues: PriorityIssue[] }
  | { kind: 'unavailable'; reason: string };

export interface SupervisoryProjectionContext {
  healthState: SystemHealthState;
  testMode: CommandCenterTestMode;
}

export interface SupervisoryProjectionClient {
  fetchProjection(
    tenantId: string,
    context: SupervisoryProjectionContext,
    signal?: AbortSignal,
  ): Promise<SupervisoryProjectionOutcome>;
}

function buildIntegrationDegradedIssue(): PriorityIssue {
  return {
    id: 'pri_integration',
    severity: 'integration_degraded',
    title: 'Integration attention needed',
    explanation: COMMAND_CENTER_COPY.integrationDegradedExplanation,
    subjectRef: 'integration_health',
    policyAuthority: 'blocked',
    actionLabel: 'Review integrations',
    actionHref: '/app/integrations',
    sourceLink: '/app/audit?filter=system_health',
    auditRef: 'aud_004',
  };
}

function buildKillSwitchPolicyIssue(): PriorityIssue {
  return {
    id: 'pri_policy_pause',
    severity: 'policy_approval_required',
    title: 'Trust API paused — policy review required',
    explanation: COMMAND_CENTER_COPY.killSwitchReadOnly,
    subjectRef: 'policy_kill_switch',
    policyAuthority: 'blocked',
    actionLabel: 'Review policy authority',
    actionHref: '/app/settings/policy',
    sourceLink: '/app/settings/policy',
    auditRef: 'aud_001',
  };
}

function resolveMockProjection(context: SupervisoryProjectionContext): PriorityIssue[] {
  const { healthState, testMode } = context;

  if (testMode === 'no_priority' || testMode === 'no_envelope') {
    return [];
  }

  if (testMode === 'kill_switch' || healthState === 'api_paused') {
    return [buildKillSwitchPolicyIssue()];
  }

  const issues: PriorityIssue[] = [...COMMAND_CENTER_PRIORITY_ISSUES];

  if (healthState === 'integration_attention') {
    issues.push(buildIntegrationDegradedIssue());
  }

  return sortPriorityIssues(issues);
}

function createDefaultSupervisoryProjectionClient(): SupervisoryProjectionClient {
  return {
    async fetchProjection(tenantId, context, signal) {
      if (signal?.aborted) {
        return { kind: 'unavailable', reason: 'Supervisory projection request aborted.' };
      }
      if (!tenantId) {
        return { kind: 'unavailable', reason: 'Tenant context required for supervisory projection.' };
      }
      return { kind: 'loaded', issues: resolveMockProjection(context) };
    },
  };
}

let defaultClient: SupervisoryProjectionClient | null = null;

export function getDefaultSupervisoryProjectionClient(): SupervisoryProjectionClient {
  if (!defaultClient) {
    defaultClient = createDefaultSupervisoryProjectionClient();
  }
  return defaultClient;
}

export function setDefaultSupervisoryProjectionClientForTests(
  client: SupervisoryProjectionClient | null,
): void {
  defaultClient = client;
}
