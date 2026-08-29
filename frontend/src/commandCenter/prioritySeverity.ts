import type { PriorityIssue, PrioritySeverity } from './types';

export const PRIORITY_SEVERITY_RANK: Record<PrioritySeverity, number> = {
  policy_approval_required: 1,
  verified_discrepancy_over_threshold: 2,
  confidence_unavailable_where_action_requested: 3,
  benchmark_source_transition: 4,
  integration_degraded: 5,
};

export function sortPriorityIssues(issues: PriorityIssue[]): PriorityIssue[] {
  return [...issues].sort(
    (a, b) => PRIORITY_SEVERITY_RANK[a.severity] - PRIORITY_SEVERITY_RANK[b.severity],
  );
}

export function validatePriorityOrder(issues: PriorityIssue[]): boolean {
  const sorted = sortPriorityIssues(issues);
  return issues.every((issue, index) => issue.id === sorted[index]?.id);
}
