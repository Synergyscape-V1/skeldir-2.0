import { POLICY_AUTHORITY_UI_LABELS } from '../lib/policyAuthorityLabels';
import type { BenchmarkEvidenceClass, DiscrepancyClass } from '../ledger/types';
import { DISCREPANCY_CLASS_LABELS } from '../claims/claimsFilterConfig';
import { evidenceClassLabel } from '../benchmarks/benchmarkDisplay';
import type { TrustIndexFilters } from './trustIndexClient';
import {
  ALLOWED_TRUST_BENCHMARK_SOURCES,
  ALLOWED_TRUST_CONFIDENCE_AVAILABILITY,
  ALLOWED_TRUST_VERIFICATION_STATUSES,
} from './trustIndexQueryState';

export const TRUST_INDEX_POLICY_LABELS = POLICY_AUTHORITY_UI_LABELS;

export const TRUST_INDEX_VERIFICATION_LABELS: Record<
  (typeof ALLOWED_TRUST_VERIFICATION_STATUSES)[number],
  string
> = {
  verified: 'Verified',
  partial: 'Partial',
  unverified: 'Unverified',
  disputed: 'Disputed',
};

export const TRUST_INDEX_CONFIDENCE_AVAILABILITY_LABELS: Record<
  (typeof ALLOWED_TRUST_CONFIDENCE_AVAILABILITY)[number],
  string
> = {
  available: 'Confidence available',
  unavailable: 'Confidence unavailable',
};

export const TRUST_INDEX_BENCHMARK_SOURCE_LABELS: Record<BenchmarkEvidenceClass, string> = {
  live_empirical: evidenceClassLabel('live_empirical'),
  tenant_longitudinal: evidenceClassLabel('tenant_longitudinal'),
  historical_prior: evidenceClassLabel('historical_prior'),
  public_prior: evidenceClassLabel('public_prior'),
  unavailable: evidenceClassLabel('unavailable'),
};

export function trustIndexDiscrepancyFilterLabel(value: DiscrepancyClass): string {
  if (value === 'within_tolerance') return '<2%';
  if (value === 'flagged') return '2–10%';
  if (value === 'material') return '>10%';
  return DISCREPANCY_CLASS_LABELS[value] ?? value;
}

export const TRUST_INDEX_DISCREPANCY_FILTER_OPTIONS: DiscrepancyClass[] = [
  'within_tolerance',
  'flagged',
  'material',
];

export function trustIndexBenchmarkSourceOptions(): Array<{ id: BenchmarkEvidenceClass; label: string }> {
  return ALLOWED_TRUST_BENCHMARK_SOURCES.map((id) => ({
    id,
    label: TRUST_INDEX_BENCHMARK_SOURCE_LABELS[id],
  }));
}

export function trustIndexActiveFilterChips(filters: TrustIndexFilters): Array<{ key: string; label: string }> {
  const chips: Array<{ key: string; label: string }> = [];
  if (filters.verificationStatus) {
    chips.push({
      key: 'verificationStatus',
      label: TRUST_INDEX_VERIFICATION_LABELS[filters.verificationStatus],
    });
  }
  if (filters.discrepancyClass) {
    chips.push({
      key: 'discrepancyClass',
      label: trustIndexDiscrepancyFilterLabel(filters.discrepancyClass),
    });
  }
  if (filters.policyAuthority) {
    chips.push({
      key: 'policyAuthority',
      label: TRUST_INDEX_POLICY_LABELS[filters.policyAuthority],
    });
  }
  if (filters.confidenceAvailability) {
    chips.push({
      key: 'confidenceAvailability',
      label: TRUST_INDEX_CONFIDENCE_AVAILABILITY_LABELS[filters.confidenceAvailability],
    });
  }
  if (filters.benchmarkSource) {
    chips.push({
      key: 'benchmarkSource',
      label: TRUST_INDEX_BENCHMARK_SOURCE_LABELS[filters.benchmarkSource],
    });
  }
  return chips;
}
