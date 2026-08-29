import { HEALTH_STATE_LABELS, OPERATIONAL_AUDIT_COPY } from './copy';
import type { SystemHealthState } from './types';

const FORBIDDEN_BY_STATE: Record<SystemHealthState, readonly string[]> = {
  operational: ['verified revenue', 'revenue verified', 'truth confirmed', 'claim invalid'],
  confidence_degraded: ['outage', 'offline', 'down', 'api paused', 'trust api paused', 'infrastructure down'],
  api_paused: ['confidence degraded', 'probabilistic', 'model outage', 'bayesian', 'confidence compute'],
  integration_attention: ['claim invalid', 'verified revenue', 'truth confirmed', 'financial truth failed'],
  unknown: ['verified revenue', 'operational dependencies are available'],
  loading: ['verified revenue'],
  fetch_failed: ['verified revenue', 'operational dependencies are available'],
};

export function healthCopyForState(state: SystemHealthState): { label: string; tooltip: string } {
  const tooltipKey = {
    operational: 'healthTooltipOperational',
    confidence_degraded: 'healthTooltipConfidenceDegraded',
    api_paused: 'healthTooltipApiPaused',
    integration_attention: 'healthTooltipIntegrationAttention',
    unknown: 'healthTooltipUnknown',
    loading: 'healthLoading',
    fetch_failed: 'healthFetchFailed',
  } as const;

  const key = tooltipKey[state];
  return {
    label: HEALTH_STATE_LABELS[state],
    tooltip: OPERATIONAL_AUDIT_COPY[key],
  };
}

export function validateHealthDomainSeparation(state: SystemHealthState): string[] {
  const { label, tooltip } = healthCopyForState(state);
  const combined = `${label} ${tooltip}`.toLowerCase();
  const forbidden = FORBIDDEN_BY_STATE[state] ?? [];
  return forbidden.filter((term) => combined.includes(term));
}

export function detectHealthDomainConflation(
  state: SystemHealthState,
  conflatedCopy: string,
): boolean {
  const combined = conflatedCopy.toLowerCase();
  const forbidden = FORBIDDEN_BY_STATE[state] ?? [];
  return forbidden.some((term) => combined.includes(term)) || combined.includes('verified revenue');
}
