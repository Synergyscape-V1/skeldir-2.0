import type {
  ExceptionCategory,
  ExceptionCategoryCounts,
  ExceptionOverviewSummary,
  ExceptionQueueRowDTO,
} from '../ledger/types';
import { isMarketerHiddenExceptionCategory } from '../benchmarks/benchmarkMarketingVisibility';
export function emptyExceptionOverviewSummary(): ExceptionOverviewSummary {
  return {
    openExceptions: 0,
    policyApprovalsRequired: 0,
    signatureFailures: 0,
    integrationRepairsNeeded: 0,
  };
}

export function computeExceptionOverviewSummary(rows: ExceptionQueueRowDTO[]): ExceptionOverviewSummary {
  const visible = rows.filter((row) => !isMarketerHiddenExceptionCategory(row.category));
  return {
    openExceptions: visible.filter((row) => row.status === 'open').length,
    policyApprovalsRequired: visible.filter((row) => row.policyAuthority === 'approval_required').length,
    signatureFailures: visible.filter((row) => row.category === 'signature_verification_failure').length,
    integrationRepairsNeeded: visible.filter((row) => row.category === 'integration_repair_needed').length,
  };
}
export function emptyExceptionCategoryCounts(): ExceptionCategoryCounts {
  return {
    all: 0,
    discrepancy_review: 0,
    policy_approval_required: 0,
    signature_verification_failure: 0,
    benchmark_source_transition: 0,
    agent_access_denied: 0,
    integration_repair_needed: 0,
  };
}

export function computeExceptionCategoryCounts(rows: ExceptionQueueRowDTO[]): ExceptionCategoryCounts {
  const visible = rows.filter((row) => !isMarketerHiddenExceptionCategory(row.category));
  const counts = emptyExceptionCategoryCounts();
  counts.all = visible.length;
  for (const row of visible) {
    counts[row.category] += 1;
  }
  return counts;
}
export function filterExceptionsByCategoryTab(
  rows: ExceptionQueueRowDTO[],
  category: ExceptionCategory | 'all',
): ExceptionQueueRowDTO[] {
  const visible = rows.filter((row) => !isMarketerHiddenExceptionCategory(row.category));
  if (category === 'all') return visible;
  return visible.filter((row) => row.category === category);
}