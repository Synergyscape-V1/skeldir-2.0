import { MAX_DETAIL_REQUESTS } from './types';

let detailRequestCount = 0;

export function resetDetailRequestCounter(): void {
  detailRequestCount = 0;
}

export function incrementDetailRequest(surface: string): void {
  detailRequestCount += 1;
  if (detailRequestCount > MAX_DETAIL_REQUESTS) {
    throw new Error(`Detail request bound exceeded for ${surface}`);
  }
}

export function getDetailRequestCount(): number {
  return detailRequestCount;
}

export function assertBoundedDetailRequestCount(): { ok: boolean; count: number } {
  return { ok: detailRequestCount <= MAX_DETAIL_REQUESTS, count: detailRequestCount };
}
