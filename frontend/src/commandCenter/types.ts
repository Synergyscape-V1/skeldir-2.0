import type { AuthorityClass, PolicyAuthorityState } from '../lib/types';
import type { RecentSignalWindow } from './recentEnvelopesConstants';
import type { BenchmarkEvidenceClass } from '../ledger/types';
import type { SystemHealthState } from '../operationalAudit/types';
import type { UnavailableVariant } from '../lib/types';

export type PrioritySeverity =
  | 'policy_approval_required'
  | 'verified_discrepancy_over_threshold'
  | 'confidence_unavailable_where_action_requested'
  | 'benchmark_source_transition'
  | 'integration_degraded';

export type CommandCenterFreshness = 'fresh' | 'stale' | 'partial';

export type CommandCenterTestMode =
  | 'default'
  | 'trust_api_failed'
  | 'kill_switch'
  | 'empty_tenant'
  | 'no_envelope'
  | 'stale'
  | 'partial'
  | 'cross_tenant_leak'
  | 'trend_unavailable'
  | 'no_priority';

export type CommandCenterOutcome =
  | { kind: 'loaded'; aggregate: CommandCenterAggregate }
  | { kind: 'loading' }
  | { kind: 'trust_api_read_failed'; message: string }
  | { kind: 'permission_denied'; message: string }
  | { kind: 'empty_tenant'; message: string }
  | { kind: 'stale'; aggregate: CommandCenterAggregate; message: string }
  | { kind: 'partial'; aggregate: CommandCenterAggregate; message: string };

export type SummaryMetricTileKind = 'financial_truth' | 'supervisory_health';

export type SupervisoryStatusBadge = 'alert' | 'transition';

interface SummaryMetricBase {
  id: string;
  label: string;
  tileKind: SummaryMetricTileKind;
  sourceSurface: 'claims_ledger' | 'trust_index' | 'exceptions_queue' | 'policy_settings';
  drillDownHref: string;
  drillDownLabel: string;
}

export interface FinancialTruthSummaryMetric extends SummaryMetricBase {
  tileKind: 'financial_truth';
  authority: AuthorityClass;
  valueMinor?: bigint;
  currencyCode?: string;
  displayValue?: string;
  subLabel?: string;
  trendDirection?: 'positive' | 'negative' | 'neutral';
  trendLabel?: string;
}

export interface SupervisoryHealthSummaryMetric extends SummaryMetricBase {
  tileKind: 'supervisory_health';
  displayValue: string;
  subLabel?: string;
  policyAuthority?: PolicyAuthorityState;
  statusBadge?: SupervisoryStatusBadge;
  valueTone?: 'default' | 'warning' | 'error' | 'success';
}

export type SummaryMetric = FinancialTruthSummaryMetric | SupervisoryHealthSummaryMetric;

export type DiscrepancyStatus = 'rejected' | 'flagged' | 'within_tolerance' | 'unavailable';
export type BayesianStatusKey = 'healthy' | 'low_confidence' | 'unavailable' | 'delayed';
export type BenchmarkStatusKey = 'stable' | 'transitioning' | 'unavailable' | 'suppressed';

export type ChannelTrustGroupBy = 'platform' | 'campaign_class' | 'commerce_rail';

export type ModelAgreementTier = 'high' | 'medium' | 'low' | 'conflict';

export interface ChannelTrustRow {
  rowId: string;
  /** @deprecated Use rowId — retained for harness selectors during migration */
  channelId: string;
  axisLabel: string;
  claimSource: string;
  campaignClass: string;
  commerceRail: string;
  detailHref?: string;
  verifiedRevenueMinor: bigint;
  currencyCode: string;
  discrepancyRateBps: number | null;
  modelAgreementTier: ModelAgreementTier;
  benchmarkValue: string | null;
  benchmarkEvidenceClass: BenchmarkEvidenceClass;
  benchmarkUnavailableReason?: string;
  policyAuthority: PolicyAuthorityState;
}

export interface PriorityIssue {
  id: string;
  severity: PrioritySeverity;
  title: string;
  explanation: string;
  /** Order, simulation, or envelope identifier from the supervisory projection. */
  subjectRef: string;
  policyAuthority: PolicyAuthorityState;
  actionLabel: string;
  actionHref: string;
  sourceLink: string;
  auditRef?: string;
}

export type TrendSnapshotStatus = 'available' | 'zero' | 'unavailable';

export interface TrendPoint {
  /** Inclusive UTC window start for this B2.10 snapshot. */
  windowStartAt: string;
  /** Exclusive UTC window end for this B2.10 snapshot. */
  windowEndAt: string;
  /** UTC calendar anchor (YYYY-MM-DD) derived from windowStartAt. */
  date: string;
  status: TrendSnapshotStatus;
  verifiedRevenueMinor: bigint;
  authority: AuthorityClass;
  sourceSurface: 'b210_revenue_snapshot';
  sourceField: 'verified_revenue_minor';
  unavailableReason?: string;
  /** Optional platform-claim overlay — unverified assertion, not deterministic truth. */
  claimedRevenueMinor?: bigint;
}

export interface VerifiedRevenueTrendMeta {
  snapshotCadenceHours: number;
  sourceField: 'verified_revenue_minor';
  /** Header-only benchmark context — never plotted on the dollar Y-axis. */
  benchmarkDiscrepancyBps?: number | null;
  claimedOverlayEnabled: boolean;
}

export type RecentEnvelopeMatchVerdict = 'matched_confirmed' | 'adjusted' | 'unmatched';

export type RecentEnvelopeTrustSignal = 'confidence_unavailable' | 'estimator_transition' | null;

export type RecentEnvelopeDrillFocus = 'evidence' | 'policy' | 'benchmark' | 'confidence';

/** @deprecated Retained for legacy envelope status badge only — not used by Recent TrustEnvelopes feed. */
export type RecentEnvelopeStatusKey = 'verified' | 'pending_approval' | 'transitioning';

export interface RecentEnvelopeRow {
  envelopeId: string;
  subjectRef: string;
  matchVerdict: RecentEnvelopeMatchVerdict;
  verifiedRevenueMinor: bigint;
  currencyCode: string;
  discrepancyRateBps: number | null;
  policyAuthority: PolicyAuthorityState;
  trustSignal: RecentEnvelopeTrustSignal;
  createdAt: string;
  auditReference: string;
}

import type { ForensicAuditEventType } from './auditActivityPolicy';

export type AuditActivityActorKind = 'user' | 'agent';

/** Visual tone for AuditActivityIcon; mirrors the .tone_* classes in AuditActivityIcon.module.css. */
export type AuditActivityTone = 'info' | 'success' | 'error' | 'refresh';

/** Tier B consequence-bearing row for the Command Center vault log strip. */
export interface AuditActivityRow {
  eventId: string;
  eventType: ForensicAuditEventType;
  occurredAt: string;
  tier: 'tier_b';
  actorKind: AuditActivityActorKind;
  /** Human email or agent display name. */
  actorDisplay: string;
  /** UUID or client id — exposed on hover/focus. */
  actorClientId: string;
  targetRef: string;
  envelopeId?: string;
}

/** @deprecated Use AuditActivityRow — retained for test override field name. */
export type AuditActivityChip = AuditActivityRow;

export interface CommandCenterAggregate {
  tenantId: string;
  lastUpdatedAt: string;
  freshness: CommandCenterFreshness;
  staleReason?: string;
  healthState: SystemHealthState;
  trustApiReadFailed: boolean;
  killSwitchActive: boolean;
  hasTrustEnvelope: boolean;
  latestEnvelopeId: string | null;
  summaryMetrics: SummaryMetric[];
  priorityIssues: PriorityIssue[];
  trendPoints: TrendPoint[];
  trendMeta?: VerifiedRevenueTrendMeta;
  trendUnavailable?: { reason: string; variant: UnavailableVariant };
  channelRows: ChannelTrustRow[];
  recentEnvelopes: RecentEnvelopeRow[];
  recentEnvelopesSignalWindow: RecentSignalWindow;
  auditActivity: AuditActivityRow[];
  openExceptionsCount: number;
  claimsReconciledCount: number;
  sourceTrace: Record<string, string>;
}

export type PrimaryActionKind =
  | 'review_issues'
  | 'review_top_issue'
  | 'view_latest_envelope'
  | 'continue_onboarding'
  | 'go_to_budget';

export interface PrimaryAction {
  kind: PrimaryActionKind;
  label: string;
  /** Present for link-based actions; omitted when the CTA opens the PriorityQueue drawer. */
  href?: string;
}
