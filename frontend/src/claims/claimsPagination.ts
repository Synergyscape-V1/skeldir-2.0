/** Supervisory claims ledger page window — aligned with Command Center row density (6–10). */
export const CLAIMS_LEDGER_MIN_PAGE_SIZE = 6;
export const CLAIMS_LEDGER_MAX_PAGE_SIZE = 10;
export const CLAIMS_LEDGER_DEFAULT_PAGE_SIZE = 10;

export function normalizeClaimsPageSize(pageSize?: number): number {
  const raw = pageSize ?? CLAIMS_LEDGER_DEFAULT_PAGE_SIZE;
  return Math.min(CLAIMS_LEDGER_MAX_PAGE_SIZE, Math.max(CLAIMS_LEDGER_MIN_PAGE_SIZE, raw));
}

export function isAllowedClaimsPageSize(pageSize: number): boolean {
  return (
    Number.isFinite(pageSize) &&
    pageSize >= CLAIMS_LEDGER_MIN_PAGE_SIZE &&
    pageSize <= CLAIMS_LEDGER_MAX_PAGE_SIZE &&
    Number.isInteger(pageSize)
  );
}
