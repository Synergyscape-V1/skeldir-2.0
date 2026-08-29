import { getDefaultOperationalAuditClient } from '../operationalAudit/operationalAuditClient';
import type { SystemHealthState } from '../operationalAudit/types';
import { ACTION_COPY } from './copy';

export type SubsystemBlockReason =
  | 'trust_api_paused'
  | 'export_unavailable'
  | 'signature_unavailable'
  | 'audit_write_unavailable'
  | 'policy_unavailable'
  | 'integration_degraded';

export interface SubsystemSafetyResult {
  safe: boolean;
  reason?: SubsystemBlockReason;
  copy?: string;
}

let testHealthOverride: SystemHealthState | null = null;
let testSubsystemFlags: Partial<Record<SubsystemBlockReason, boolean>> = {};

export function setSubsystemHealthForTests(state: SystemHealthState | null): void {
  testHealthOverride = state;
}

export function setSubsystemBlockForTests(flags: Partial<Record<SubsystemBlockReason, boolean>>): void {
  testSubsystemFlags = flags;
}

export function resetSubsystemSafetyForTests(): void {
  testHealthOverride = null;
  testSubsystemFlags = {};
}

export async function checkSubsystemSafetyForExternalAction(
  tenantId: string,
  requiresSignature = false,
  requiresAuditWrite = true,
): Promise<SubsystemSafetyResult> {
  if (testSubsystemFlags.trust_api_paused) {
    return { safe: false, reason: 'trust_api_paused', copy: ACTION_COPY.subsystemUnsafe };
  }
  if (testSubsystemFlags.export_unavailable) {
    return { safe: false, reason: 'export_unavailable', copy: ACTION_COPY.subsystemUnsafe };
  }
  if (requiresSignature && testSubsystemFlags.signature_unavailable) {
    return { safe: false, reason: 'signature_unavailable', copy: ACTION_COPY.subsystemUnsafe };
  }
  if (requiresAuditWrite && testSubsystemFlags.audit_write_unavailable) {
    return { safe: false, reason: 'audit_write_unavailable', copy: ACTION_COPY.subsystemUnsafe };
  }
  if (testSubsystemFlags.policy_unavailable) {
    return { safe: false, reason: 'policy_unavailable', copy: ACTION_COPY.subsystemUnsafe };
  }

  const healthState = testHealthOverride ?? (await resolveHealthState(tenantId));
  if (healthState === 'api_paused') {
    return { safe: false, reason: 'trust_api_paused', copy: ACTION_COPY.subsystemUnsafe };
  }
  if (healthState === 'integration_attention' && testSubsystemFlags.integration_degraded !== false) {
    return { safe: false, reason: 'integration_degraded', copy: ACTION_COPY.subsystemUnsafe };
  }
  return { safe: true };
}

async function resolveHealthState(tenantId: string): Promise<SystemHealthState> {
  const outcome = await getDefaultOperationalAuditClient().getSystemHealth(tenantId);
  if (outcome.kind === 'health_operational') return 'operational';
  if (outcome.kind === 'health_confidence_degraded') return 'confidence_degraded';
  if (outcome.kind === 'health_api_paused') return 'api_paused';
  if (outcome.kind === 'health_integration_attention') return 'integration_attention';
  if (outcome.kind === 'health_loading') return 'loading';
  if (outcome.kind === 'health_fetch_failed') return 'fetch_failed';
  return 'unknown';
}
