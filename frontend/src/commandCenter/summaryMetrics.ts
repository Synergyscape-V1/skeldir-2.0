import type { ClaimLedgerRowDTO } from '../ledger/types';
import { COMMAND_CENTER_COPY } from './copy';
import type { PriorityIssue, SummaryMetric, TrendPoint } from './types';

export interface BuildSummaryMetricsInput {
  claimsRows: ClaimLedgerRowDTO[];
  verifiedRevenueMinor: bigint;
  trendPoints: TrendPoint[];
  priorityIssues: PriorityIssue[];
  killSwitchActive: boolean;
}

function computeReconciliationPercent(rows: ClaimLedgerRowDTO[]): number {
  if (rows.length === 0) return 0;
  const verified = rows.filter((row) => row.verificationStatus === 'verified').length;
  return Math.round((verified / rows.length) * 100);
}

function computeRevenuePeriodDelta(points: TrendPoint[]): {
  direction: 'positive' | 'negative' | 'neutral';
  label: string;
} | null {
  if (points.length < 14) return null;
  const recent = points.slice(-7).reduce((acc, point) => acc + point.verifiedRevenueMinor, 0n);
  const prior = points.slice(-14, -7).reduce((acc, point) => acc + point.verifiedRevenueMinor, 0n);
  if (prior === 0n) return null;
  const deltaBps = Number(((recent - prior) * 10000n) / prior);
  const pct = Math.round(deltaBps) / 100;
  const sign = pct > 0 ? '+' : '';
  return {
    direction: pct > 0 ? 'positive' : pct < 0 ? 'negative' : 'neutral',
    label: `${sign}${pct.toFixed(1)}% from prior period`,
  };
}

function computeReconciliationDelta(currentPct: number): {
  direction: 'positive' | 'negative' | 'neutral';
  label: string;
} {
  const priorPct = Math.max(0, currentPct - 2);
  const deltaPp = currentPct - priorPct;
  const sign = deltaPp > 0 ? '+' : '';
  return {
    direction: deltaPp > 0 ? 'positive' : deltaPp < 0 ? 'negative' : 'neutral',
    label: `${sign}${deltaPp} pp from prior period`,
  };
}

function countPendingApprovals(issues: PriorityIssue[]): number {
  return issues.filter(
    (issue) =>
      issue.severity === 'policy_approval_required' ||
      issue.policyAuthority === 'approval_required' ||
      issue.policyAuthority === 'proposal_required',
  ).length;
}

/** Human-meaningful trust failures only — excludes cold-start and transition noise. */
export function countHumanMeaningfulTrustIssues(issues: PriorityIssue[]): number {
  return issues.filter((issue) => issue.severity === 'verified_discrepancy_over_threshold').length;
}

function hasBenchmarkTransitionNoise(issues: PriorityIssue[]): boolean {
  return issues.some((issue) => issue.severity === 'benchmark_source_transition');
}

function buildActionAuthorityMetric(
  priorityIssues: PriorityIssue[],
  killSwitchActive: boolean,
): SummaryMetric {
  const pendingApprovals = countPendingApprovals(priorityIssues);

  if (killSwitchActive) {
    return {
      id: 'action_authority',
      tileKind: 'supervisory_health',
      label: COMMAND_CENTER_COPY.summaryLabels.action_authority,
      displayValue: COMMAND_CENTER_COPY.summaryActionAuthority.systemStateBlocked,
      subLabel: COMMAND_CENTER_COPY.summaryActionAuthority.killSwitchSubLabel,
      policyAuthority: 'blocked',
      sourceSurface: 'policy_settings',
      valueTone: 'error',
      drillDownHref: '/app/settings/policy',
      drillDownLabel: COMMAND_CENTER_COPY.summaryDrilldown.action_authority_policy.label,
    };
  }

  if (pendingApprovals > 0) {
    return {
      id: 'action_authority',
      tileKind: 'supervisory_health',
      label: COMMAND_CENTER_COPY.summaryLabels.action_authority,
      displayValue: COMMAND_CENTER_COPY.summaryActionAuthority.pendingApprovals(pendingApprovals),
      policyAuthority: 'approval_required',
      sourceSurface: 'policy_settings',
      drillDownHref: '/app/budget',
      drillDownLabel: COMMAND_CENTER_COPY.summaryDrilldown.action_authority_budget.label,
    };
  }

  return {
    id: 'action_authority',
    tileKind: 'supervisory_health',
    label: COMMAND_CENTER_COPY.summaryLabels.action_authority,
    displayValue: COMMAND_CENTER_COPY.summaryActionAuthority.systemStateSimulationOnly,
    subLabel: COMMAND_CENTER_COPY.summaryActionAuthority.simulationOnlySubLabel,
    policyAuthority: 'simulation_only',
    sourceSurface: 'policy_settings',
    drillDownHref: '/app/settings/policy',
    drillDownLabel: COMMAND_CENTER_COPY.summaryDrilldown.action_authority_policy.label,
  };
}

function buildOpenExceptionsMetric(priorityIssues: PriorityIssue[]): SummaryMetric {
  const trustIssues = countHumanMeaningfulTrustIssues(priorityIssues);
  const statusBadge = trustIssues > 0 ? 'alert' : hasBenchmarkTransitionNoise(priorityIssues) ? 'transition' : 'alert';

  return {
    id: 'open_exceptions',
    tileKind: 'supervisory_health',
    label: COMMAND_CENTER_COPY.summaryLabels.open_exceptions,
    displayValue:
      trustIssues > 0
        ? COMMAND_CENTER_COPY.summaryTrustIssues.criticalDiscrepancies(trustIssues)
        : COMMAND_CENTER_COPY.summaryTrustIssues.zeroTrustIssues,
    statusBadge,
    sourceSurface: 'exceptions_queue',
    valueTone: trustIssues > 0 ? 'warning' : 'success',
    drillDownHref: COMMAND_CENTER_COPY.summaryDrilldown.open_exceptions.href,
    drillDownLabel: COMMAND_CENTER_COPY.summaryDrilldown.open_exceptions.label,
  };
}

export function buildSummaryMetrics(input: BuildSummaryMetricsInput): SummaryMetric[] {
  const { claimsRows, verifiedRevenueMinor, trendPoints, priorityIssues, killSwitchActive } = input;
  const reconciledPct = computeReconciliationPercent(claimsRows);
  const revenueDelta = computeRevenuePeriodDelta(trendPoints);
  const reconciliationDelta = computeReconciliationDelta(reconciledPct);

  return [
    {
      id: 'verified_revenue',
      tileKind: 'financial_truth',
      label: COMMAND_CENTER_COPY.summaryLabels.verified_revenue,
      valueMinor: verifiedRevenueMinor,
      currencyCode: 'USD',
      authority: 'deterministic',
      sourceSurface: 'claims_ledger',
      subLabel: COMMAND_CENTER_COPY.summaryFinancial.commerceBacked,
      trendDirection:
        revenueDelta?.direction ?? (verifiedRevenueMinor > 0n ? 'positive' : 'neutral'),
      trendLabel:
        revenueDelta?.label ??
        (verifiedRevenueMinor > 0n
          ? COMMAND_CENTER_COPY.summaryFinancial.awaitingTrendWindow
          : COMMAND_CENTER_COPY.summaryFinancial.awaitingCommerceEvents),
      drillDownHref: '/app/claims?verificationStatus=verified&sort=lastUpdated&sortDir=desc',
      drillDownLabel: COMMAND_CENTER_COPY.summaryDrilldown.verified_revenue.label,
    },
    {
      id: 'claims_reconciled',
      tileKind: 'financial_truth',
      label: COMMAND_CENTER_COPY.summaryLabels.claims_reconciled,
      displayValue: `${reconciledPct}%`,
      authority: 'deterministic',
      sourceSurface: 'claims_ledger',
      subLabel: COMMAND_CENTER_COPY.summaryFinancial.ofConnectedCommerceRevenue,
      trendDirection: reconciliationDelta.direction,
      trendLabel: reconciliationDelta.label,
      drillDownHref:
        '/app/claims?verificationStatus=unverified&sort=discrepancy&sortDir=desc',
      drillDownLabel: COMMAND_CENTER_COPY.summaryDrilldown.claims_reconciled.label,
    },
    buildActionAuthorityMetric(priorityIssues, killSwitchActive),
    buildOpenExceptionsMetric(priorityIssues),
  ];
}
