import type { UnavailableConfidenceCauseBreakdown } from '../ledger/types';
import { TRUST_ENVELOPE_INDEX_COPY } from './copy';

export type UnavailableConfidenceDisposition =
  | 'zero'
  | 'cold_start_dominant'
  | 'computation_dominant'
  | 'mixed'
  | 'other';

export function resolveUnavailableConfidenceDisposition(
  count: number,
  causes: UnavailableConfidenceCauseBreakdown,
): UnavailableConfidenceDisposition {
  if (count <= 0) return 'zero';
  const cold = causes.coldStart;
  const computation = causes.computation;
  const other = causes.other;

  if (cold > 0 && computation === 0 && other === 0) return 'cold_start_dominant';
  if (computation > 0 && cold === 0 && other === 0) return 'computation_dominant';
  if (cold > 0 && computation > 0) return 'mixed';
  if (cold >= computation && cold >= other && cold > 0) return 'cold_start_dominant';
  if (computation >= cold && computation >= other && computation > 0) return 'computation_dominant';
  return 'other';
}

export function unavailableConfidenceMetaCopy(
  disposition: UnavailableConfidenceDisposition,
  causes: UnavailableConfidenceCauseBreakdown,
): string {
  const copy = TRUST_ENVELOPE_INDEX_COPY.summary;
  switch (disposition) {
    case 'zero':
      return copy.unavailableConfidenceZeroMeta;
    case 'cold_start_dominant':
      return copy.unavailableConfidenceColdStartMeta;
    case 'computation_dominant':
      return copy.unavailableConfidenceComputationMeta;
    case 'mixed':
      return copy.unavailableConfidenceMixedMeta(causes.coldStart, causes.computation);
    default:
      return copy.unavailableConfidenceOtherMeta;
  }
}

/** Value tone: warn only when computation failures are present / dominant — not for expected cold start. */
export function unavailableConfidenceValueTone(
  disposition: UnavailableConfidenceDisposition,
): 'default' | 'warning' {
  if (disposition === 'computation_dominant' || disposition === 'mixed') return 'warning';
  return 'default';
}

export function unavailableConfidenceMetaTone(
  disposition: UnavailableConfidenceDisposition,
): 'default' | 'success' | 'warning' {
  if (disposition === 'zero') return 'success';
  if (disposition === 'computation_dominant' || disposition === 'mixed') return 'warning';
  return 'default';
}
