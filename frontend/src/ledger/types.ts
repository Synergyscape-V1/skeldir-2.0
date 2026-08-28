import type { AuthorityClass, PolicyAuthorityState } from '../lib/types';

/** Shared query metadata echoed by every Level 7 list boundary */
export interface LedgerQueryMetadata {
  pageSize: number;
  offset: number;
  totalCount: number;
  hasMore: boolean;
  appliedFilters: Record<string, string | undefined>;
  appliedSort: { key: string; direction: 'asc' | 'desc' };
  stableSortKey: string;
  queryId: string;
}

export interface LedgerPageParams {
  offset?: number;
  pageSize?: number;
  sortKey?: string;
  sortDirection?: 'asc' | 'desc';
  search?: string;
}

export type FutureDetailAffordanceState =
  | 'detail_blocked_level_8'
  | 'action_blocked_level_9';

export interface ConfidenceShape {
  status: 'available' | 'unavailable' | 'delayed';
  authority?: AuthorityClass;
  reason?: string;
  intervalLower?: number;
  intervalUpper?: number;
  methodOrContext?: string;
  qualitativeState?: string;
}

export interface BenchmarkShape {
  status: 'available' | 'unavailable' | 'suppressed';
  rawBenchmark?: string;
  decisionSafeBenchmark?: string;
  evidenceClass?: string;
  coverageClass?: string;
  suppressionReason?: string;
  comparability?: string;
  sourceTransition?: boolean;
  transitionReason?: string;
  reason?: string;
}

export type BenchmarkEvidenceClass =
  | 'live_empirical'
  | 'tenant_longitudinal'
  | 'historical_prior'
  | 'public_prior'
  | 'unavailable';

export type BenchmarkCoverageClass = 'exact' | 'broad' | 'tenant_only' | 'prior' | 'insufficient';

export type BenchmarkComparability = 'comparable' | 'not_comparable' | 'source_changed' | 'unavailable';

export type BenchmarkSuppressionReasonCode = 'low_k' | 'dominance_risk' | 'policy_excluded' | 'sparse_data';

export type BenchmarkActionability = 'simulate' | 'observe_only_until_stable' | 'blocked';

export type LedgerOutcomeKind =
  | 'loaded'
  | 'loading'
  | 'empty'
  | 'filtered_empty'
  | 'partial'
  | 'permission_denied'
  | 'scope_denied'
  | 'policy_unavailable'
  | 'audit_unavailable'
  | 'trust_api_error'
  | 'network_error'
  | 'schema_invalid'
  | 'payload_oversized'
  | 'query_invalid'
  | 'sort_invalid'
  | 'unknown_error';

export interface LoadedLedgerResult<TRow> extends LedgerQueryMetadata {
  kind: 'loaded';
  rows: TRow[];
}

export interface EmptyLedgerResult extends LedgerQueryMetadata {
  kind: 'empty';
  rows: [];
}

export interface FilteredEmptyLedgerResult extends LedgerQueryMetadata {
  kind: 'filtered_empty';
  rows: [];
}

export interface PartialLedgerResult<TRow> extends LedgerQueryMetadata {
  kind: 'partial';
  rows: TRow[];
  partialReason: string;
}

export interface ErrorLedgerResult {
  kind: Exclude<
    LedgerOutcomeKind,
    'loaded' | 'loading' | 'empty' | 'filtered_empty' | 'partial'
  >;
  message: string;
}

export type LedgerListOutcome<TRow> =
  | LoadedLedgerResult<TRow>
  | EmptyLedgerResult
  | FilteredEmptyLedgerResult
  | PartialLedgerResult<TRow>
  | ErrorLedgerResult;

export type DiscrepancyClass = 'within_tolerance' | 'flagged' | 'material' | 'unknown';

export type MatchVerdictStatus =
  | 'verified'
  | 'within_tolerance'
  | 'flagged'
  | 'rejected'
  | 'unavailable';

export interface ClaimLedgerRowDTO {
  claimRef: string;
  claimTime: string;
  /** Platform that delivered the claim (Meta Ads, Google Ads, …). */
  claimSource: string;
  /** Marketing campaign class (Paid Search, Creator, Branded, …). */
  campaignClass: string;
  /** How the customer arrived at commerce (Organic, Direct, Referral, …). */
  commerceRail: string;
  /** Commerce/payment integration truth source (Shopify, Stripe, …). */
  commerceSource: string;
  claimedRevenueMinor: bigint;
  verifiedRevenueMinor: bigint;
  currencyCode: string;
  discrepancyAmountMinor: bigint;
  discrepancyRateBps: number;
  discrepancyClass: DiscrepancyClass;
  matchVerdict: MatchVerdictStatus;
  attributionModel: string;
  verificationStatus: 'verified' | 'partial' | 'unverified' | 'disputed';
  confidence: ConfidenceShape;
  policyAuthority: PolicyAuthorityState;
  auditReference: string;
  lastUpdated: string;
  futureDetailAffordance: FutureDetailAffordanceState;
}

export type AuditRecordStatus = 'linked' | 'pending_review' | 'unavailable';

export type TrustEnvelopeMatchVerdict =
  | 'matched_confirmed'
  | 'matched_provisional'
  | 'adjusted'
  | 'unmatched';

export type TrustEnvelopeVerificationStatus = 'verified' | 'partial' | 'unverified' | 'disputed';

export interface TrustEnvelopeIndexRowDTO {
  envelopeId: string;
  subjectRef: string;
  subjectLabel: string;
  subjectDetail: string;
  /** UTC claim timestamp — forensic precision; never relative. */
  claimTime: string;
  /** Platform that delivered the revenue claim (canonical backend key). */
  claimSource: string;
  /** Authoritative platform-claimed revenue in minor units. */
  claimedRevenueMinor: bigint;
  verifiedRevenueMinor: bigint;
  currencyCode: string;
  discrepancyAmountMinor: bigint;
  discrepancyRateBps: number;
  discrepancyClass: DiscrepancyClass;
  matchVerdict: TrustEnvelopeMatchVerdict;
  verificationStatus: TrustEnvelopeVerificationStatus;
  revenueAuthority: AuthorityClass;
  attributionModel: string;
  attributionAuthority: AuthorityClass;
  confidence: ConfidenceShape;
  benchmark: BenchmarkShape;
  auditRecordStatus: AuditRecordStatus;
  policyAuthority: PolicyAuthorityState;
  /** @deprecated Use claimSource — retained for list DTO migration. */
  channelSource: string;
  auditReference: string;
  generationTimestamp: string;
  status: 'active' | 'superseded' | 'invalid';
  futureDetailAffordance: FutureDetailAffordanceState;
}

export type UnavailableConfidenceCauseClass = 'cold_start' | 'computation' | 'other';

export interface UnavailableConfidenceCauseBreakdown {
  coldStart: number;
  computation: number;
  other: number;
}

export interface TrustEnvelopeIndexSummary {
  totalCount: number;
  addedLast24h: number;
  verifiedRevenueMinor: bigint;
  currencyCode: string;
  auditLinkedCount: number;
  auditPendingReviewCount: number;
  /** Envelopes with confidence not available (confidence-only; excludes benchmark-only gaps). */
  unavailableConfidenceCount: number;
  unavailableConfidenceCauses: UnavailableConfidenceCauseBreakdown;
}

export type ChannelDiscrepancyStatus = 'rejected' | 'flagged' | 'within_tolerance' | 'unavailable';
export type ChannelBayesianStatusKey = 'healthy' | 'low_confidence' | 'unavailable' | 'delayed' | 'degraded';
export type ChannelBenchmarkStatusKey =
  | 'stable'
  | 'transitioning'
  | 'unavailable'
  | 'suppressed'
  | 'attention_needed';

export interface ChannelOverviewRowDTO {
  channelId: string;
  /** Display label for the attribution / traffic-type dimension. */
  channelName: string;
  /** Canonical attribution-channel key (orthogonal to claimSource). */
  attributionChannel: string;
  /** Platform claim source that delivered the revenue claim. */
  claimSource: string;
  commerceSource?: string;
  verifiedRevenueMinor: bigint;
  claimedRevenueMinor: bigint;
  currencyCode: string;
  discrepancyClass: DiscrepancyClass;
  discrepancyRateBps: number;
  discrepancyStatus: ChannelDiscrepancyStatus;
  attributionModelAgreement: string;
  bayesianStatusKey: ChannelBayesianStatusKey;
  bayesianStabilityLabel?: string;
  benchmarkStatusKey: ChannelBenchmarkStatusKey;
  benchmarkPositionLabel?: string;
  confidence: ConfidenceShape;
  benchmark: BenchmarkShape;
  relatedClaimsCount: number;
  relatedEnvelopeCount: number;
  auditReference: string;
  policyAuthority: PolicyAuthorityState;
  actionability: 'observe_only' | 'proposal_required' | 'blocked';
  futureDetailAffordance: FutureDetailAffordanceState;
}

export interface ChannelOverviewSummary {
  highestVerifiedRevenueChannelId: string | null;
  highestVerifiedRevenueChannelName: string | null;
  highestVerifiedRevenueMinor: bigint;
  highestVerifiedRevenueDeltaLabel?: string;
  largestDiscrepancyChannelId: string | null;
  largestDiscrepancyChannelName: string | null;
  largestDiscrepancyRateBps: number;
  largestDiscrepancyComparisonLabel?: string;
  lowestConfidenceChannelId: string | null;
  lowestConfidenceChannelName: string | null;
  lowestConfidenceLabel: string;
  bestActionReadyChannelId: string | null;
  bestActionReadyChannelName: string | null;
  bestActionReadyRevenueMinor: bigint;
  bestActionReadyPolicyAuthority: PolicyAuthorityState | null;
  bestActionReadyBenchmarkLabel?: string;
  currencyCode: string;
}

export interface BenchmarkRowDTO {
  benchmarkId: string;
  benchmarkName: string;
  segmentName: string;
  rawBenchmark?: string;
  decisionSafeBenchmark?: string;
  evidenceClass: BenchmarkEvidenceClass;
  coverageClass: BenchmarkCoverageClass;
  suppressionReason?: string;
  suppressionReasonCode?: BenchmarkSuppressionReasonCode;
  rollupLevel?: string;
  adjustmentReason?: string;
  comparability: BenchmarkComparability;
  sourceTransition: boolean;
  transitionReason?: string;
  actionability: BenchmarkActionability;
  policyAuthority: PolicyAuthorityState;
  lastRefreshed: string;
  channelId?: string;
  platformId?: string;
  commerceSourceId?: string;
  trustEnvelopeId?: string;
  auditReference?: string;
  benchmark: BenchmarkShape;
}

export type ExceptionCategory =
  | 'discrepancy_review'
  | 'policy_approval_required'
  | 'signature_verification_failure'
  | 'benchmark_source_transition'
  | 'agent_access_denied'
  | 'integration_repair_needed';

export type ExceptionSeverity = 'critical' | 'warning' | 'info';

export type ExceptionActionKind = 'review' | 'open';

export interface ExceptionQueueRowDTO {
  exceptionId: string;
  category: ExceptionCategory;
  severity: ExceptionSeverity;
  summary: string;
  affectedObjectLabel: string;
  lastAuditEvent: string;
  subject: string;
  source: string;
  sourceObjectType?: string;
  policyAuthority: PolicyAuthorityState;
  auditReference: string;
  createdAt: string;
  status: 'open' | 'acknowledged' | 'suppressed' | 'resolved';
  actionKind: ExceptionActionKind;
  futureDetailAffordance: FutureDetailAffordanceState;
  futureActionAffordance: FutureDetailAffordanceState;
}

export interface ExceptionOverviewSummary {
  openExceptions: number;
  policyApprovalsRequired: number;
  signatureFailures: number;
  integrationRepairsNeeded: number;
}

export interface ExceptionCategoryCounts {
  all: number;
  discrepancy_review: number;
  policy_approval_required: number;
  signature_verification_failure: number;
  benchmark_source_transition: number;
  agent_access_denied: number;
  integration_repair_needed: number;
}

export interface BudgetInputAvailabilityDTO {
  dateRangeStart: string;
  dateRangeEnd: string;
  eligibleChannels: string[];
  spendConstraintMinor?: bigint;
  currencyCode: string;
  objective: string;
  minimumVerifiedRevenueWindowMinor: bigint;
  policyAuthority: PolicyAuthorityState;
  simulationAvailability: 'available' | 'blocked_insufficient_data' | 'blocked_policy';
  blockedReason?: string;
  validationErrors: string[];
}
