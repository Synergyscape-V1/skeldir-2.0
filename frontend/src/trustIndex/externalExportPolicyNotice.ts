import type { PolicyAuthorityState } from '../lib/types';
import type { PolicySettings } from '../governance/types';
import { TRUST_ENVELOPE_INDEX_COPY } from './copy';

const AUTHORITY_NOTICE_LABELS: Record<PolicyAuthorityState, string> = {
  blocked: 'blocked',
  simulation_only: 'simulation only',
  proposal_required: 'proposal required',
  approval_required: 'pending certification',
  auto_executable_within_policy: 'auto-executable within policy',
};

export function resolveExternalExportAuthority(policy: PolicySettings): PolicyAuthorityState {
  const externalExport = policy.categories.find((category) => category.category === 'external_export');
  return externalExport?.authority ?? 'blocked';
}

export function formatExternalExportPolicyNotice(authority: PolicyAuthorityState): string {
  return TRUST_ENVELOPE_INDEX_COPY.policyExportNotice(AUTHORITY_NOTICE_LABELS[authority]);
}
