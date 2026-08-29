import type { ExceptionCategory, ExceptionCategoryCounts, ExceptionQueueRowDTO } from '../ledger/types';

/** Exception categories routed to audit only — not marketer-facing tickets. */
export const MARKETER_HIDDEN_EXCEPTION_CATEGORIES: readonly ExceptionCategory[] = [
  'benchmark_source_transition',
] as const;

export function isMarketerHiddenExceptionCategory(
  category: ExceptionCategory,
): category is (typeof MARKETER_HIDDEN_EXCEPTION_CATEGORIES)[number] {
  return (MARKETER_HIDDEN_EXCEPTION_CATEGORIES as readonly string[]).includes(category);
}

export function filterMarketerVisibleExceptions(
  rows: ExceptionQueueRowDTO[],
): ExceptionQueueRowDTO[] {
  return rows.filter((row) => !isMarketerHiddenExceptionCategory(row.category));
}

export function filterMarketerVisibleExceptionCategories(
  categories: readonly ExceptionCategory[],
): ExceptionCategory[] {
  return categories.filter((category) => !isMarketerHiddenExceptionCategory(category));
}

export function adjustExceptionCategoryCountsForMarketer(
  counts: ExceptionCategoryCounts,
): ExceptionCategoryCounts {
  const hidden = counts.benchmark_source_transition;
  if (hidden === 0) return counts;
  return {
    ...counts,
    all: Math.max(0, counts.all - hidden),
    benchmark_source_transition: 0,
  };
}
