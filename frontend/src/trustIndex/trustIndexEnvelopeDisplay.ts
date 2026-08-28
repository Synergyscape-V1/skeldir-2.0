import type { PolicyAuthorityState } from '../lib/types';
import { claimSourceLabel } from '../claims/claimsLedgerDisplay';
import { formatBpsAsPercentOneDecimal } from '../lib/money';
import type {
  ConfidenceShape,
  DiscrepancyClass,
  TrustEnvelopeIndexRowDTO,
  TrustEnvelopeMatchVerdict,
} from '../ledger/types';

export const TRUST_INDEX_ATTRIBUTION_DISCLAIMER =
  'Deterministic heuristic. Does not prove causal lift.';

export const TRUST_INDEX_DEFAULT_SORT_KEY = 'trust_envelope_priority';

const POLICY_SORT_ORDER: Record<PolicyAuthorityState, number> = {
  approval_required: 0,
  proposal_required: 1,
  blocked: 2,
  simulation_only: 3,
  auto_executable_within_policy: 4,
};

const DISCREPANCY_SORT_ORDER: Record<DiscrepancyClass, number> = {
  material: 0,
  flagged: 1,
  within_tolerance: 2,
  unknown: 3,
};

export function trustIndexPolicySortRank(state: PolicyAuthorityState): number {
  return POLICY_SORT_ORDER[state] ?? 99;
}

export function trustIndexDiscrepancySortRank(row: TrustEnvelopeIndexRowDTO): number {
  return DISCREPANCY_SORT_ORDER[row.discrepancyClass] ?? 99;
}

export function sortTrustEnvelopeIndexRows(
  rows: TrustEnvelopeIndexRowDTO[],
): TrustEnvelopeIndexRowDTO[] {
  return [...rows].sort((a, b) => {
    const policyDelta = trustIndexPolicySortRank(a.policyAuthority) - trustIndexPolicySortRank(b.policyAuthority);
    if (policyDelta !== 0) return policyDelta;

    const discrepancyDelta = trustIndexDiscrepancySortRank(a) - trustIndexDiscrepancySortRank(b);
    if (discrepancyDelta !== 0) return discrepancyDelta;

    const bpsDelta = b.discrepancyRateBps - a.discrepancyRateBps;
    if (bpsDelta !== 0) return bpsDelta;

    return b.claimTime.localeCompare(a.claimTime);
  });
}

export function trustEnvelopeSortComparator(
  a: TrustEnvelopeIndexRowDTO,
  b: TrustEnvelopeIndexRowDTO,
  key: string,
  direction: 'asc' | 'desc',
): number {
  if (key === TRUST_INDEX_DEFAULT_SORT_KEY) {
    const delta = sortTrustEnvelopeIndexRows([a, b])[0] === a ? -1 : 1;
    return direction === 'desc' ? delta : -delta;
  }

  if (key === 'claimTime' || key === 'generationTimestamp' || key === 'date') {
    const delta = a.claimTime.localeCompare(b.claimTime);
    return direction === 'desc' ? -delta : delta;
  }

  if (key === 'discrepancyRateBps') {
    const delta = a.discrepancyRateBps - b.discrepancyRateBps;
    return direction === 'desc' ? -delta : delta;
  }

  if (key === 'policyAuthority') {
    const delta = trustIndexPolicySortRank(a.policyAuthority) - trustIndexPolicySortRank(b.policyAuthority);
    return direction === 'asc' ? delta : -delta;
  }

  const delta = a.envelopeId.localeCompare(b.envelopeId);
  return direction === 'desc' ? -delta : delta;
}

export function formatTrustIndexClaimSourceLabel(claimSource: string): string {
  return claimSourceLabel(claimSource);
}

export function formatTrustIndexDifferencePercent(discrepancyRateBps: number): string {
  return formatBpsAsPercentOneDecimal(Math.abs(discrepancyRateBps));
}

export function trustIndexDifferenceSeverityClass(
  discrepancyClass: DiscrepancyClass,
): 'within_tolerance' | 'flagged' | 'rejected' {
  if (discrepancyClass === 'within_tolerance') return 'within_tolerance';
  if (discrepancyClass === 'flagged') return 'flagged';
  return 'rejected';
}

export function formatMatchVerdictLabel(verdict: TrustEnvelopeMatchVerdict): string {
  return verdict;
}

export function confidenceUnavailableReason(confidence: ConfidenceShape): string {
  if (confidence.status === 'delayed') {
    return confidence.reason ?? 'Bayesian computation delayed.';
  }
  if (confidence.reason === 'cold_start_insufficient_data') {
    return 'Cold start due to insufficient data.';
  }
  if (confidence.reason === 'bayesian_timeout') {
    return 'Bayesian timeout before posterior converged.';
  }
  return confidence.reason ?? 'Confidence unavailable for this envelope.';
}

export function truncateSignatureHash(hash?: string): string {
  if (!hash) return 'Signature hash unavailable';
  if (hash.length <= 12) return hash;
  return `${hash.slice(0, 6)}…${hash.slice(-4)}`;
}
