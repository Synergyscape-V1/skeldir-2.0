import { describe, expect, it } from 'vitest';
import {
  adjustExceptionCategoryCountsForMarketer,
  filterMarketerVisibleExceptions,
  isMarketerHiddenExceptionCategory,
} from '../benchmarks/benchmarkMarketingVisibility';

describe('benchmarkMarketingVisibility', () => {
  it('treats benchmark_source_transition as marketer-hidden', () => {
    expect(isMarketerHiddenExceptionCategory('benchmark_source_transition')).toBe(true);
    expect(isMarketerHiddenExceptionCategory('discrepancy_review')).toBe(false);
  });

  it('filters hidden exception rows from marketer queue', () => {
    const rows = filterMarketerVisibleExceptions([
      {
        exceptionId: 'ex_1',
        category: 'discrepancy_review',
        severity: 'warning',
        status: 'open',
        summary: 'Review discrepancy',
        affectedObjectLabel: 'claim_1',
        sourceObjectType: 'claim',
        policyAuthority: 'blocked',
        lastAuditEvent: 'aud_1',
        createdAt: '2026-01-01',
        ageLabel: '1d',
      },
      {
        exceptionId: 'ex_2',
        category: 'benchmark_source_transition',
        severity: 'info',
        status: 'open',
        summary: 'Benchmark source changed',
        affectedObjectLabel: 'linkedin',
        sourceObjectType: 'channel',
        policyAuthority: 'blocked',
        lastAuditEvent: 'aud_2',
        createdAt: '2026-01-02',
        ageLabel: '2d',
      },
    ] as never);

    expect(rows).toHaveLength(1);
    expect(rows[0]?.category).toBe('discrepancy_review');
  });

  it('adjusts category counts to exclude hidden benchmark transitions', () => {
    const adjusted = adjustExceptionCategoryCountsForMarketer({
      all: 3,
      discrepancy_review: 2,
      policy_approval_required: 0,
      signature_verification_failure: 0,
      benchmark_source_transition: 1,
      agent_access_denied: 0,
      integration_repair_needed: 0,
    });

    expect(adjusted.all).toBe(2);
    expect(adjusted.benchmark_source_transition).toBe(0);
  });
});
