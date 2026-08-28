import { describe, expect, it } from 'vitest';
import { CANONICAL_EXCEPTION_FIXTURES } from '../exceptions/exceptionsFixtures';
import {
  buildExceptionDetailFromQueueRow,
  EXCEPTION_CATEGORY_NEXT_REVIEW,
  recommendedNextReviewForCategory,
} from '../exceptions/exceptionDetailGuidance';
import type { ExceptionCategory } from '../ledger/types';

const ATTRIBUTION_LEAK = /attribution model/i;

describe('exceptionDetailGuidance', () => {
  it('binds detail category and summary to the queue row — not a generic reconciliation stub', () => {
    const integration = CANONICAL_EXCEPTION_FIXTURES.find(
      (row) => row.category === 'integration_repair_needed',
    );
    expect(integration).toBeTruthy();
    const detail = buildExceptionDetailFromQueueRow(integration!, 'tenant_1');
    expect(detail.category).toBe('integration_repair_needed');
    expect(detail.evidenceSummary).toBe(integration!.summary);
    expect(detail.evidenceSummary).not.toMatch(/reconciliation/i);
    expect(detail.recommendedNextReview.join(' ')).not.toMatch(ATTRIBUTION_LEAK);
    expect(detail.recommendedNextReview.some((step) => /integration/i.test(step))).toBe(true);
  });

  it('keeps attribution-oriented guidance only on discrepancy_review', () => {
    const categories = Object.keys(EXCEPTION_CATEGORY_NEXT_REVIEW) as ExceptionCategory[];
    for (const category of categories) {
      const steps = recommendedNextReviewForCategory(category).join(' ');
      if (category === 'discrepancy_review') {
        expect(steps).toMatch(/commerce|revenue|claim/i);
      } else {
        expect(steps).not.toMatch(ATTRIBUTION_LEAK);
      }
    }
  });

  it('maps every fixture id to category-specific next review', () => {
    for (const row of CANONICAL_EXCEPTION_FIXTURES) {
      const detail = buildExceptionDetailFromQueueRow(row, 'tenant_1');
      expect(detail.exceptionId).toBe(row.exceptionId);
      expect(detail.category).toBe(row.category);
      expect(detail.recommendedNextReview).toEqual([...EXCEPTION_CATEGORY_NEXT_REVIEW[row.category]]);
    }
  });
});
