import type { TrustEnvelopeIndexRowDTO } from '../ledger/types';
import type { TrustIndexFilters } from './trustIndexClient';

export function buildTrustIndexFilterRecord(
  filters: TrustIndexFilters,
): Record<string, string | undefined> {
  return {
    status: filters.status,
    verificationStatus: filters.verificationStatus,
    discrepancyClass: filters.discrepancyClass,
    policyAuthority: filters.policyAuthority,
    confidenceAvailability: filters.confidenceAvailability,
    benchmarkSource: filters.benchmarkSource,
  };
}

export function matchesTrustIndexRow(
  row: TrustEnvelopeIndexRowDTO,
  filters: Record<string, string | undefined>,
): boolean {
  if (filters.status && row.status !== filters.status) return false;

  if (filters.verificationStatus && row.verificationStatus !== filters.verificationStatus) return false;
  if (filters.discrepancyClass && row.discrepancyClass !== filters.discrepancyClass) return false;
  if (filters.policyAuthority && row.policyAuthority !== filters.policyAuthority) return false;

  if (filters.confidenceAvailability) {
    const available = row.confidence.status === 'available';
    if (filters.confidenceAvailability === 'available' && !available) return false;
    if (filters.confidenceAvailability === 'unavailable' && available) return false;
  }

  if (filters.benchmarkSource) {
    const evidenceClass =
      row.benchmark.status === 'available' ? row.benchmark.evidenceClass : 'unavailable';
    if (evidenceClass !== filters.benchmarkSource) return false;
  }

  return true;
}

export function hasActiveTrustIndexFilters(filters: TrustIndexFilters): boolean {
  return Boolean(
    filters.status ||
      filters.verificationStatus ||
      filters.discrepancyClass ||
      filters.policyAuthority ||
      filters.confidenceAvailability ||
      filters.benchmarkSource,
  );
}
