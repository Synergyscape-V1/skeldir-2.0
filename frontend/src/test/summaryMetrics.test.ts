import { describe, expect, it } from 'vitest';
import { baseClaimRow } from '../claims/claimsClient';
import { COMMAND_CENTER_PRIORITY_ISSUES } from '../commandCenter/commandCenterPriorityFixtures';
import {
  buildSummaryMetrics,
  countHumanMeaningfulTrustIssues,
} from '../commandCenter/summaryMetrics';

describe('summaryMetrics', () => {
  it('splits financial truth and supervisory health tile kinds', () => {
    const claimsRows = [baseClaimRow(0), baseClaimRow(1), baseClaimRow(2), baseClaimRow(3)];
    const metrics = buildSummaryMetrics({
      claimsRows,
      verifiedRevenueMinor: 12_842_000n,
      trendPoints: [],
      priorityIssues: COMMAND_CENTER_PRIORITY_ISSUES,
      killSwitchActive: false,
    });

    expect(metrics.map((metric) => metric.tileKind)).toEqual([
      'financial_truth',
      'financial_truth',
      'supervisory_health',
      'supervisory_health',
    ]);
  });

  it('renders reconciliation as percent with commerce sub-label and filtered drill-down', () => {
    const claimsRows = Array.from({ length: 4 }, (_, index) => baseClaimRow(index));
    const metrics = buildSummaryMetrics({
      claimsRows,
      verifiedRevenueMinor: 1n,
      trendPoints: [],
      priorityIssues: [],
      killSwitchActive: false,
    });
    const reconciled = metrics.find((metric) => metric.id === 'claims_reconciled');
    expect(reconciled?.tileKind).toBe('financial_truth');
    if (reconciled?.tileKind === 'financial_truth') {
      expect(reconciled.displayValue).toMatch(/%$/);
      expect(reconciled.subLabel).toBe('Of connected commerce revenue');
      expect(reconciled.trendLabel).toMatch(/pp from prior period/);
      expect(reconciled.drillDownHref).toContain('verificationStatus=unverified');
    }
  });

  it('uses pending approvals for action authority when proposals exist', () => {
    const metrics = buildSummaryMetrics({
      claimsRows: [],
      verifiedRevenueMinor: 0n,
      trendPoints: [],
      priorityIssues: COMMAND_CENTER_PRIORITY_ISSUES,
      killSwitchActive: false,
    });
    const actionAuthority = metrics.find((metric) => metric.id === 'action_authority');
    expect(actionAuthority?.tileKind).toBe('supervisory_health');
    if (actionAuthority?.tileKind === 'supervisory_health') {
      expect(actionAuthority.displayValue).toMatch(/Pending Certification/);
      expect(actionAuthority.policyAuthority).toBe('approval_required');
      expect(actionAuthority.drillDownHref).toBe('/app/budget');
      expect(actionAuthority.trendLabel).toBeUndefined();
    }
  });

  it('counts only human-meaningful trust issues for open exceptions tile', () => {
    expect(countHumanMeaningfulTrustIssues(COMMAND_CENTER_PRIORITY_ISSUES)).toBe(1);
    const metrics = buildSummaryMetrics({
      claimsRows: [],
      verifiedRevenueMinor: 0n,
      trendPoints: [],
      priorityIssues: COMMAND_CENTER_PRIORITY_ISSUES,
      killSwitchActive: false,
    });
    const openExceptions = metrics.find((metric) => metric.id === 'open_exceptions');
    if (openExceptions?.tileKind === 'supervisory_health') {
      expect(openExceptions.displayValue).toBe('1 Critical Discrepancy');
      expect(openExceptions.drillDownHref).toBe('/app/exceptions');
      expect(openExceptions.statusBadge).toBe('alert');
    }
  });

  it('shows explicit zero trust issues healthy state', () => {
    const metrics = buildSummaryMetrics({
      claimsRows: [],
      verifiedRevenueMinor: 0n,
      trendPoints: [],
      priorityIssues: [],
      killSwitchActive: false,
    });
    const openExceptions = metrics.find((metric) => metric.id === 'open_exceptions');
    if (openExceptions?.tileKind === 'supervisory_health') {
      expect(openExceptions.displayValue).toBe('0 Trust Issues');
    }
  });
});
