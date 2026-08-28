export const EXCEPTIONS_DEFAULT_PAGE_SIZE = 6;
export const EXCEPTIONS_PAGE_SIZE_OPTIONS = [6, 12, 24] as const;
export const EXCEPTIONS_MAX_PAGE_SIZE = 24;

export function normalizeExceptionsPageSize(pageSize?: number): number {
  if (!pageSize || pageSize < 1) return EXCEPTIONS_DEFAULT_PAGE_SIZE;
  return Math.min(pageSize, EXCEPTIONS_MAX_PAGE_SIZE);
}
