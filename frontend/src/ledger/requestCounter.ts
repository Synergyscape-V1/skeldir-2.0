/** Test instrumentation — bounded request count per page render */
let requestCount = 0;
const MAX_REQUESTS_PER_PAGE = 3;

export function resetLedgerRequestCounter(): void {
  requestCount = 0;
}

export function incrementLedgerRequest(surface: string): void {
  requestCount += 1;
  if (requestCount > MAX_REQUESTS_PER_PAGE) {
    throw new Error(`Ledger request budget exceeded for ${surface}: ${requestCount}`);
  }
}

export function getLedgerRequestCount(): number {
  return requestCount;
}

export function assertBoundedRequestCount(max = MAX_REQUESTS_PER_PAGE): { ok: boolean; count: number } {
  return { ok: requestCount <= max, count: requestCount };
}

export { MAX_REQUESTS_PER_PAGE };
