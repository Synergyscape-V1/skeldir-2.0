import type { BenchmarkShape, ConfidenceShape } from '../ledger/types';
import type { BenchmarkStatusKey } from '../commandCenter/types';
import { formatClaimTimeUtcLines } from '../claims/claimsLedgerDisplay';
import { TRUST_ENVELOPE_INDEX_COPY } from './copy';

export function formatTrustEnvelopeCreatedOn(iso: string): { dateLine: string; timeLine: string } | null {
  return formatClaimTimeUtcLines(iso);
}

export function formatTrustIndexConfidencePercent(confidence: ConfidenceShape): string | null {
  if (confidence.status !== 'available') return null;
  if (confidence.intervalLower !== undefined && confidence.intervalUpper !== undefined) {
    const midpoint = (confidence.intervalLower + confidence.intervalUpper) / 2;
    return `${Math.round(midpoint * 100)}%`;
  }
  return null;
}

export function benchmarkToTableStatus(benchmark: BenchmarkShape): BenchmarkStatusKey {
  if (benchmark.status === 'unavailable') return 'unavailable';
  if (benchmark.status === 'suppressed') return 'suppressed';
  if (benchmark.sourceTransition) return 'transitioning';
  return 'stable';
}

export function benchmarkTableLabel(benchmark: BenchmarkShape): string | null {
  if (benchmark.status === 'unavailable') return null;
  if (benchmark.status === 'suppressed') return null;
  if (benchmark.decisionSafeBenchmark) return benchmark.decisionSafeBenchmark;
  return 'Not defined';
}

export function formatAuditLinkLabel(_auditReference?: string): string {
  return TRUST_ENVELOPE_INDEX_COPY.table.auditLinkLabel;
}
