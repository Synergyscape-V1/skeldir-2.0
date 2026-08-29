import type { AuthorityClass, PolicyAuthorityState } from '../lib/types';

export interface BudgetSimulationFormState {
  dateRangeStart: string;
  dateRangeEnd: string;
  channelIds: string[];
  spendConstraintMinor: bigint;
  currencyCode: string;
  objectiveId: string;
  verifiedRevenueWindowDays: number;
}

export type SufficiencyGateStatus = 'passed' | 'available' | 'failed' | 'pending';

export interface SufficiencyGateRow {
  id: string;
  label: string;
  status: SufficiencyGateStatus;
  detail: string;
}

export type SufficiencySummaryState =
  | 'empty'
  | 'loading'
  | 'eligible'
  | 'blocked'
  | 'partial'
  | 'error';

export interface SufficiencySummary {
  state: SufficiencySummaryState;
  rows: SufficiencyGateRow[];
}

export interface AllocationRow {
  channelId: string;
  channelLabel: string;
  amountMinor: bigint;
  shareBps: number;
  color: string;
}

export type ContributionRole = 'primary' | 'supporting';

export interface SourceTrustEnvelopeRow {
  envelopeId: string;
  channelId: string;
  channelLabel: string;
  authority: AuthorityClass;
  contributionRole: ContributionRole;
  verifiedRevenueMinor: bigint;
}

export type AuditArtifactStatus = 'written' | 'pending' | 'unavailable';

export interface ConfidenceInterval {
  lowerBps: number;
  upperBps: number;
  authority: AuthorityClass;
}

export interface SensitivityRange {
  optimisticBps: number;
  pessimisticBps: number;
  authority: AuthorityClass;
}

export interface BudgetSimulationResultDTO {
  simulationId: string;
  versionStamp: string;
  currencyCode: string;
  currentAllocation: AllocationRow[];
  simulatedAllocation: AllocationRow[];
  // Baseline values for comparative reasoning
  currentBlendedRoasBps: number;
  currentTotalRevenueMinor: bigint;
  currentBlendedCacBps: number;
  // Projected values
  projectedBlendedRoasBps: number;
  projectedTotalRevenueMinor: bigint;
  projectedBlendedCacBps: number;
  // Delta values (calculated from baseline and projected)
  expectedRevenueLiftBps: number;
  blendedCacChangeBps: number;
  spendDeltaBps: number;
  // Confidence and sensitivity (optional based on model type)
  confidenceInterval?: ConfidenceInterval;
  sensitivityRange?: SensitivityRange;
  impactAuthority: AuthorityClass;
  sourceTrustEnvelopes: SourceTrustEnvelopeRow[];
  policyAuthority: PolicyAuthorityState;
  auditReference: string;
  auditArtifactStatus: AuditArtifactStatus;
}

export type GenerateSimulationOutcome =
  | { kind: 'success'; result: BudgetSimulationResultDTO }
  | { kind: 'blocked_sparse_data'; message: string }
  | { kind: 'trust_api_error'; message: string }
  | { kind: 'permission_denied'; message: string }
  | { kind: 'error'; message: string };
