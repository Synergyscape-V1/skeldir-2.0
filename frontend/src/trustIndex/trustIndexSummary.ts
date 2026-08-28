import type {
  TrustEnvelopeIndexRowDTO,
  TrustEnvelopeIndexSummary,
  UnavailableConfidenceCauseClass,
  UnavailableConfidenceCauseBreakdown,
} from '../ledger/types';

type ConfidenceShape = TrustEnvelopeIndexRowDTO['confidence'];

export function isConfidenceUnavailable(confidence: ConfidenceShape): boolean {
  return confidence.status !== 'available';
}

/** Maps row confidence reasons to supervisor-facing cause classes. */
export function classifyUnavailableConfidenceCause(
  confidence: ConfidenceShape,
): UnavailableConfidenceCauseClass {
  if (!isConfidenceUnavailable(confidence)) {
    throw new Error('classifyUnavailableConfidenceCause requires unavailable confidence');
  }
  if (confidence.status === 'delayed' || confidence.reason === 'bayesian_timeout') {
    return 'computation';
  }
  if (confidence.reason === 'cold_start_insufficient_data') {
    return 'cold_start';
  }
  return 'other';
}

export function emptyUnavailableConfidenceCauses(): UnavailableConfidenceCauseBreakdown {
  return { coldStart: 0, computation: 0, other: 0 };
}

export function computeTrustIndexSummary(rows: TrustEnvelopeIndexRowDTO[]): TrustEnvelopeIndexSummary {
  const now = Date.now();
  const dayMs = 86_400_000;
  let verifiedRevenueMinor = 0n;
  let auditLinkedCount = 0;
  let auditPendingReviewCount = 0;
  let unavailableConfidenceCount = 0;
  const unavailableConfidenceCauses = emptyUnavailableConfidenceCauses();
  let addedLast24h = 0;

  for (const row of rows) {
    verifiedRevenueMinor += row.verifiedRevenueMinor;
    if (row.auditRecordStatus === 'linked') auditLinkedCount += 1;
    if (row.auditRecordStatus === 'pending_review') auditPendingReviewCount += 1;
    if (isConfidenceUnavailable(row.confidence)) {
      unavailableConfidenceCount += 1;
      const cause = classifyUnavailableConfidenceCause(row.confidence);
      if (cause === 'cold_start') unavailableConfidenceCauses.coldStart += 1;
      else if (cause === 'computation') unavailableConfidenceCauses.computation += 1;
      else unavailableConfidenceCauses.other += 1;
    }
    if (now - new Date(row.generationTimestamp).getTime() <= dayMs) addedLast24h += 1;
  }

  return {
    totalCount: rows.length,
    addedLast24h,
    verifiedRevenueMinor,
    currencyCode: rows[0]?.currencyCode ?? 'USD',
    auditLinkedCount,
    auditPendingReviewCount,
    unavailableConfidenceCount,
    unavailableConfidenceCauses,
  };
}

export function emptyTrustIndexSummary(): TrustEnvelopeIndexSummary {
  return {
    totalCount: 0,
    addedLast24h: 0,
    verifiedRevenueMinor: 0n,
    currencyCode: 'USD',
    auditLinkedCount: 0,
    auditPendingReviewCount: 0,
    unavailableConfidenceCount: 0,
    unavailableConfidenceCauses: emptyUnavailableConfidenceCauses(),
  };
}
