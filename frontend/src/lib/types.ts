export type AuthorityClass =
  | 'deterministic'
  | 'probabilistic'
  | 'benchmark'
  | 'prior'
  | 'unavailable'
  | 'suppressed';

export const AUTHORITY_CLASSES: readonly AuthorityClass[] = [
  'deterministic',
  'probabilistic',
  'benchmark',
  'prior',
  'unavailable',
  'suppressed',
];

export type PolicyAuthorityState =
  | 'blocked'
  | 'simulation_only'
  | 'proposal_required'
  | 'approval_required'
  | 'auto_executable_within_policy';

export const POLICY_AUTHORITY_STATES: readonly PolicyAuthorityState[] = [
  'blocked',
  'simulation_only',
  'proposal_required',
  'approval_required',
  'auto_executable_within_policy',
];

export type TenantPolicyMode = 'design_partner' | 'full';

export type UnavailableVariant =
  | 'default'
  | 'no_confidence'
  | 'no_benchmark'
  | 'no_commerce_truth'
  | 'no_platform_claims'
  | 'suppressed'
  | 'sparse_data'
  | 'partial_data'
  | 'blocked_simulation';

export type ToastSeverity = 'success' | 'error' | 'info' | 'warning';

export type LoadingPhase = 'idle' | 'under_2s' | 'over_2s' | 'over_8s';

export type EvidenceEventStatus = 'success' | 'warning' | 'error' | 'info';

export interface EvidenceTimelineItem {
  timestamp: string;
  eventType: string;
  source: string;
  result: string;
  evidenceRef: string;
  status?: EvidenceEventStatus;
}

export interface DataUnavailablePanelProps {
  reason?: string;
  whatStillWorks?: string;
  nextEligibleAt?: string;
  userAction?: {
    label: string;
    onClick: () => void;
    disabled?: boolean;
  };
  variant?: UnavailableVariant;
}
