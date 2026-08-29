import type {
  BenchmarkShape,
  ConfidenceShape,
  DiscrepancyClass,
} from '../ledger/types';
import type { PolicyAuthorityState, AuthorityClass } from '../lib/types';

export const MAX_TIMELINE_ITEMS = 50;
export const MAX_RELATED_ITEMS = 25;
export const MAX_DETAIL_REQUESTS = 3;

export type DetailOutcomeKind =
  | 'loaded'
  | 'loading'
  | 'long_loading'
  | 'not_found'
  | 'permission_denied'
  | 'scope_denied'
  | 'unavailable'
  | 'schema_invalid'
  | 'object_id_mismatch'
  | 'stale_version'
  | 'corrupted_evidence'
  | 'audit_unavailable'
  | 'confidence_unavailable'
  | 'benchmark_unavailable'
  | 'network_error'
  | 'trust_api_error';

export interface DetailErrorOutcome {
  kind: Exclude<DetailOutcomeKind, 'loaded' | 'loading' | 'long_loading'>;
  message: string;
}

export interface AttributionTabData {
  selectedModel: string;
  agreementTier: string;
  modelAssumption: string;
  causalStatus: string;
  negativeBoundaryCopy: string;
  availableModels?: string[];
}

/** Executive claim detail — paid media budget lever (platform × campaign class). */
export interface ClaimPaidAttributionRow {
  platform: string;
  campaignClass: string;
  amountMinor: bigint;
  channelId: string;
}

/** Executive claim detail — non-paid commerce rail (reality check; not a budget line). */
export interface ClaimJourneyOriginRow {
  commerceRail: string;
  amountMinor: bigint;
}

/** @deprecated Prefer paidAttribution + journeyOrigins two-tier disclosure. */
export interface ClaimAttributionChannelRow {
  channel: string;
  amountMinor: bigint;
}

export type ClaimEventMatchStatus = 'matched' | 'unmatched';

/** Executive claim detail — reconciled platform ad events. */
export interface ClaimEventRow {
  id: string;
  label: string;
  occurredAt: string;
  claimedMinor: bigint;
  matchStatus: ClaimEventMatchStatus;
}

export type ClaimExecutiveVerdict = 'verified' | 'discrepancy' | 'unverified';

export type ClaimEvidencePhase = 'intake' | 'verification' | 'record';

export interface ClaimEvidenceStep {
  plainLabel: string;
  timestamp: string;
  evidenceRef: string;
  phase?: ClaimEvidencePhase;
  badge?: string;
  href?: string;
  hrefLabel?: string;
}

export interface ClaimTechnicalIdentifiers {
  envelopeId: string | null;
  tenantIdHash: string | null;
}

/** Human-facing operator projection for trust envelope detail (no forensic fields). */
export interface TrustEnvelopeOperatorView {
  envelopeId: string;
  canonicalEnvelopeId?: string;
  tenantId: string;
  status: 'issued' | 'superseded' | 'invalid';
  createdAt: string;
  auditReference: string;
  subject: TrustEnvelopeSubjectData;
  deterministicTruth: TrustEnvelopeDeterministicTruthData;
  attribution: TrustEnvelopeAttributionData;
  confidence: TrustEnvelopeConfidenceData;
  benchmark: TrustEnvelopeBenchmarkData;
  policyAuthority: TrustEnvelopePolicyAuthorityData;
  versionStamp: string;
}

export interface AuditTabData {
  auditReference: string;
  accessEvents: Array<{ timestamp: string; actor: string; action: string }>;
}

export interface ClaimDetailDTO {
  claimId: string;
  tenantId: string;
  claimSource: string;
  claimRef: string;
  verificationStatus: 'verified' | 'partial' | 'unverified' | 'disputed';
  claimedRevenueMinor: bigint;
  verifiedRevenueMinor: bigint;
  currencyCode: string;
  discrepancyAmountMinor: bigint;
  discrepancyRateBps: number;
  discrepancyClass: DiscrepancyClass;
  commerceEvidenceSource: string;
  /** Default deterministic attribution model label (display only — no switcher). */
  defaultAttributionModel: string;
  /** Verified paid media — budget levers (platform × campaign class). */
  paidAttribution: ClaimPaidAttributionRow[];
  /** Non-paid journey origins — reality check against platform inflation. */
  journeyOrigins: ClaimJourneyOriginRow[];
  claimEvents: ClaimEventRow[];
  /** Present when verificationStatus === 'unverified'. */
  unverifiedReason?: string;
  /** Legacy operator fields retained for fixture/export substrate compatibility. */
  policyAuthority: PolicyAuthorityState;
  confidence: ConfidenceShape;
  benchmark: BenchmarkShape;
  attribution: AttributionTabData;
  audit: AuditTabData;
  incrementalityBoundaryCopy: string;
  summaryCopy: string;
  verifiedNarrative: string;
  evidenceSteps: ClaimEvidenceStep[];
  technicalIdentifiers: ClaimTechnicalIdentifiers;
  auditSecuredAt: string;
  versionStamp: string;
}

export interface LoadedClaimDetailOutcome {
  kind: 'loaded';
  detail: ClaimDetailDTO;
}

export type ClaimDetailOutcome = LoadedClaimDetailOutcome | DetailErrorOutcome;

export interface TrustEnvelopeJsonAuthorityAmount {
  amountMinor: number;
  currencyCode: string;
  authority: string;
}

export interface TrustEnvelopeJsonAuthorityValue {
  value: string | number;
  authority: string;
}

export interface TrustEnvelopeJsonProvenanceEntry {
  timestamp: string;
  eventType: string;
  source: string;
  result: string;
  evidenceReference: string;
}

export interface TrustEnvelopeJsonContract {
  envelopeId: string;
  canonicalEnvelopeId: string | null;
  status: string;
  createdAt: string;
  tenantId: string;
  schemaVersion: string;
  subject: {
    subjectType: string;
    identifier: string;
    relatedClaimId: string;
    relatedChannel: {
      label: string;
      channelId: string;
    };
    sourceSystems: string[];
    timeWindow: {
      start: string;
      end: string;
      timezone: string;
    };
  };
  deterministicTruth: {
    verifiedRevenue: TrustEnvelopeJsonAuthorityAmount;
    claimComparison: {
      claimedRevenue: TrustEnvelopeJsonAuthorityAmount;
      verifiedRevenue: TrustEnvelopeJsonAuthorityAmount;
      difference: TrustEnvelopeJsonAuthorityAmount & { rateBps: number };
    };
    commerceEvidenceSource: string;
  };
  attributionModel: {
    selectedModel: string;
    modelFamily: string;
    agreementTier: string;
    allocationResult: {
      channel: string;
      allocationPercent: number;
      authority: string;
    };
    boundaryNote: string;
  };
  confidenceMetadata: {
    status: string;
    credibleInterval95: [number, number] | null;
    posteriorSupport: number | null;
    modelFreshness: string | null;
    authority: string;
    note: string;
    fallbackReason: string | null;
  };
  benchmarkMetadata: {
    rawBenchmark: TrustEnvelopeJsonAuthorityValue;
    decisionSafeBenchmark: TrustEnvelopeJsonAuthorityValue;
    sourceClass: string;
    coverageClass: string;
    suppressionReason: string | null;
    comparableToPrevious: boolean;
    actionability: string;
  };
  policyAuthority: {
    state: string;
    explanation: string;
    allowedActions: string[];
    blockedActions: string[];
    auditRequirement: string;
  };
  provenanceChain: TrustEnvelopeJsonProvenanceEntry[] | null;
  auditAndSignature: {
    auditReference: string;
    accessEvents: number;
    artifactRef: string | null;
    artifactHash: string | null;
    signature: string | null;
    signatureAlgorithm: string | null;
    keyId: string | null;
    canonicalizationVersion: string;
    semanticTruthHash: string;
    signatureHash: string | null;
  };
}

export interface TrustEnvelopeAttributionData {
  selectedModel: string;
  modelFamily: string;
  modelAgreementTier: string;
  allocationChannel: string;
  allocationPercent: number;
  allocationAuthority: AuthorityClass;
  boundaryNote: string;
}

export interface TrustEnvelopeConfidenceData {
  status: 'available' | 'unavailable' | 'delayed';
  intervalLower?: number;
  intervalUpper?: number;
  posteriorSupport?: number;
  modelFreshnessAt?: string;
  authority: AuthorityClass;
  boundaryNote: string;
  reason?: string;
}

export interface TrustEnvelopeBenchmarkData {
  status: 'available' | 'unavailable' | 'suppressed';
  rawBenchmark: string;
  decisionSafeBenchmark: string;
  benchmarkAuthority: AuthorityClass;
  sourceClass: string;
  coverageClass: string;
  suppressionReason: string | null;
  comparableToPrevious: boolean;
  actionability: string;
  reason?: string;
}

export interface TrustEnvelopePolicyAuthorityData {
  state: PolicyAuthorityState;
  explanation: string;
  allowedActions: string[];
  blockedActions: string[];
  auditRequirement: string;
}

export interface TrustEnvelopeDeterministicTruthData {
  verifiedRevenueMinor: bigint;
  claimedRevenueMinor: bigint;
  differenceMinor: bigint;
  differenceRateBps: number;
  currencyCode: string;
  matchVerdictStatus: string;
  extractionFreshness?: 'fresh' | 'stale' | 'failed';
  matchQuality?: 'high' | 'medium' | 'low';
  commerceEvidenceSource: string;
}

export interface TrustEnvelopeSubjectData {
  subjectType: string;
  subjectIdentifier: string;
  relatedClaimId: string;
  relatedClaimHref: string;
  relatedChannelLabel: string;
  relatedChannelHref: string;
  sourceSystem: string;
  timeWindowLabel: string;
}

/** @alias TrustEnvelopeOperatorView — human-facing trust envelope detail contract. */
export type TrustEnvelopeDetailDTO = TrustEnvelopeOperatorView;

export interface LoadedTrustEnvelopeDetailOutcome {
  kind: 'loaded';
  detail: TrustEnvelopeDetailDTO;
}

export type TrustEnvelopeDetailOutcome = LoadedTrustEnvelopeDetailOutcome | DetailErrorOutcome;

export interface AttributionModelComparisonRow {
  model: string;
  verifiedRevenueAllocatedMinor: bigint;
  shareOfVerifiedRevenueBps: number;
  modelAssumption: string;
  agreementTier: string;
}

export interface ChannelDetailDTO {
  channelId: string;
  tenantId: string;
  channelName: string;
  authorityStatus: string;
  verifiedRevenueOverTime: Array<{ period: string; verifiedRevenueMinor: bigint }>;
  reconciliation: {
    claimedRevenueMinor: bigint;
    verifiedRevenueMinor: bigint;
    currencyCode: string;
    discrepancyClass: DiscrepancyClass;
  };
  modelComparison: AttributionModelComparisonRow[];
  modelComparisonCopy: string;
  confidence: ConfidenceShape;
  benchmark: BenchmarkShape;
  relatedClaims: Array<{ claimRef: string; verificationStatus: string }>;
  relatedEnvelopes: Array<{ envelopeId: string; status: string }>;
  policyAuthority: PolicyAuthorityState;
  auditReference: string;
  versionStamp: string;
}

export interface LoadedChannelDetailOutcome {
  kind: 'loaded';
  detail: ChannelDetailDTO;
}

export type ChannelDetailOutcome = LoadedChannelDetailOutcome | DetailErrorOutcome;

export interface ExceptionDetailDTO {
  exceptionId: string;
  tenantId: string;
  category: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  affectedObject: string;
  createdAt: string;
  reviewState: string;
  policyAuthority: PolicyAuthorityState;
  evidenceSummary: string;
  auditReference: string;
  recommendedNextReview: string[];
  versionStamp: string;
}

export interface LoadedExceptionDetailOutcome {
  kind: 'loaded';
  detail: ExceptionDetailDTO;
}

export type ExceptionDetailOutcome = LoadedExceptionDetailOutcome | DetailErrorOutcome;

export interface BudgetSimulationDetailDTO {
  simulationId: string;
  tenantId: string;
  simulationStatus: 'ready' | 'blocked_insufficient_data' | 'blocked_policy';
  inputAssumptions: string[];
  verifiedRevenueBasisMinor: bigint;
  currencyCode: string;
  confidence: ConfidenceShape;
  benchmark: BenchmarkShape;
  policyAuthority: PolicyAuthorityState;
  projectedAllocation: Array<{ channel: string; shareBps: number }>;
  riskCaveats: string[];
  auditReference: string;
  blockedReason?: string;
  versionStamp: string;
}

export interface LoadedBudgetSimulationDetailOutcome {
  kind: 'loaded';
  detail: BudgetSimulationDetailDTO;
}

export type BudgetSimulationDetailOutcome =
  | LoadedBudgetSimulationDetailOutcome
  | DetailErrorOutcome;
