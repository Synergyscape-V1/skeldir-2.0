export const BENCHMARKS_DEFAULT_PAGE_SIZE = 8;
export const BENCHMARKS_MAX_PAGE_SIZE = 50;
export const BENCHMARKS_PAGE_SIZE_OPTIONS = [8, 16, 24] as const;

export function normalizeBenchmarksPageSize(value: number): number {
  if (!Number.isFinite(value) || value < 1) return BENCHMARKS_DEFAULT_PAGE_SIZE;
  return Math.min(Math.floor(value), BENCHMARKS_MAX_PAGE_SIZE);
}

export function benchmarksTotalPages(totalCount: number, pageSize: number): number {
  if (pageSize < 1) return 1;
  const pages = ((totalCount + pageSize - 1) / pageSize) | 0;
  return pages < 1 ? 1 : pages;
}

export function benchmarksCurrentPage(offset: number, pageSize: number): number {
  if (pageSize < 1) return 1;
  return ((offset / pageSize) | 0) + 1;
}
