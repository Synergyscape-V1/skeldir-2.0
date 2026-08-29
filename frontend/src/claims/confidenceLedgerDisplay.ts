import type { ConfidenceShape } from '../ledger/types';
import { CLAIMS_CONFIDENCE_LEDGER_COPY } from './copy';

export type ClaimsConfidenceDisposition =
  | 'available_exact'
  | 'available_stable'
  | 'available_wide'
  | 'cold_start'
  | 'insufficient_data'
  | 'worker_failure'
  | 'computation_timeout'
  | 'refit_locked'
  | 'delayed'
  | 'unavailable_other';

export type ClaimsConfidenceColorTone =
  | 'success'
  | 'probabilistic'
  | 'info'
  | 'warning'
  | 'error'
  | 'neutral';

export interface ClaimsConfidenceLedgerProjection {
  disposition: ClaimsConfidenceDisposition;
  colorTone: ClaimsConfidenceColorTone;
  shortLabel: string;
  title: string;
  intervalLabel: string | null;
}

function normalizeReasonKey(reason?: string): string {
  return reason?.trim().toLowerCase().replace(/-/g, '_').replace(/\s+/g, '_') ?? '';
}

function formatIntervalPercent(value: number): string {
  const pct = value <= 1 ? value * 100 : value;
  const rounded = Math.round(pct * 10) / 10;
  return Number.isInteger(rounded) ? `${rounded}` : rounded.toFixed(1);
}

export function formatConfidenceIntervalLabel(
  lower?: number,
  upper?: number,
): string | null {
  if (lower === undefined || upper === undefined) return null;
  return `${formatIntervalPercent(lower)}–${formatIntervalPercent(upper)}%`;
}

function intervalMidpoint(confidence: ConfidenceShape): number | null {
  if (confidence.intervalLower === undefined || confidence.intervalUpper === undefined) {
    return null;
  }
  return (confidence.intervalLower + confidence.intervalUpper) / 2;
}

function resolveUnavailableDisposition(reasonKey: string): ClaimsConfidenceDisposition {
  if (reasonKey.includes('cold_start')) return 'cold_start';
  if (reasonKey.includes('refit_locked') || reasonKey.includes('refit_lock')) return 'refit_locked';
  if (reasonKey.includes('worker_failure') || reasonKey.includes('worker_fail')) return 'worker_failure';
  if (reasonKey.includes('timeout') || reasonKey.includes('timed_out')) return 'computation_timeout';
  if (
    reasonKey === 'insufficient_data' ||
    reasonKey === 'unavailable_insufficient_data' ||
    reasonKey.includes('insufficient_data') ||
    reasonKey === 'bayesian_not_available'
  ) {
    return 'insufficient_data';
  }
  return 'unavailable_other';
}

export function resolveClaimsConfidenceDisposition(
  confidence: ConfidenceShape,
): ClaimsConfidenceDisposition {
  if (confidence.status === 'delayed') return 'delayed';
  if (confidence.status === 'unavailable') {
    return resolveUnavailableDisposition(normalizeReasonKey(confidence.reason));
  }

  const qualitative = normalizeReasonKey(confidence.qualitativeState);
  if (qualitative.includes('exact_bucket')) {
    return 'available_exact';
  }

  const midpoint = intervalMidpoint(confidence);
  if (midpoint !== null && midpoint < 0.7) {
    return 'available_wide';
  }

  return 'available_stable';
}

function colorToneForDisposition(disposition: ClaimsConfidenceDisposition): ClaimsConfidenceColorTone {
  switch (disposition) {
    // Available posteriors share the probabilistic register — never success/deterministic green.
    case 'available_exact':
    case 'available_stable':
    case 'available_wide':
      return 'probabilistic';
    case 'cold_start':
    case 'delayed':
      return 'info';
    case 'refit_locked':
      return 'warning';
    case 'worker_failure':
    case 'computation_timeout':
      return 'error';
    default:
      return 'neutral';
  }
}

export function resolveClaimsConfidenceLedgerProjection(
  confidence: ConfidenceShape,
): ClaimsConfidenceLedgerProjection {
  const disposition = resolveClaimsConfidenceDisposition(confidence);
  const colorTone = colorToneForDisposition(disposition);
  const intervalLabel = formatConfidenceIntervalLabel(
    confidence.intervalLower,
    confidence.intervalUpper,
  );
  const copy = CLAIMS_CONFIDENCE_LEDGER_COPY;

  switch (disposition) {
    case 'available_exact':
      return {
        disposition,
        colorTone,
        intervalLabel,
        shortLabel: intervalLabel ? copy.availableIntervalShort(intervalLabel) : '—',
        title: copy.availableExactTitle(intervalLabel ?? '—', confidence.methodOrContext),
      };
    case 'available_stable':
      return {
        disposition,
        colorTone,
        intervalLabel,
        shortLabel: intervalLabel ? copy.availableIntervalShort(intervalLabel) : copy.unavailableOtherShort,
        title: copy.availableStableTitle(
          intervalLabel ?? '—',
          confidence.methodOrContext,
          confidence.qualitativeState,
        ),
      };
    case 'available_wide':
      return {
        disposition,
        colorTone,
        intervalLabel,
        shortLabel: intervalLabel ? copy.availableIntervalShort(intervalLabel) : '—',
        title: copy.availableWideTitle(
          intervalLabel ?? '—',
          confidence.qualitativeState ?? confidence.methodOrContext,
        ),
      };
    case 'cold_start':
      return {
        disposition,
        colorTone,
        intervalLabel: null,
        shortLabel: copy.coldStartShort,
        title: copy.coldStartTitle(confidence.reason),
      };
    case 'insufficient_data':
      return {
        disposition,
        colorTone,
        intervalLabel: null,
        shortLabel: copy.insufficientDataShort,
        title: copy.insufficientDataTitle(confidence.reason),
      };
    case 'worker_failure':
      return {
        disposition,
        colorTone,
        intervalLabel: null,
        shortLabel: copy.workerFailureShort,
        title: copy.workerFailureTitle(confidence.reason),
      };
    case 'computation_timeout':
      return {
        disposition,
        colorTone,
        intervalLabel: null,
        shortLabel: copy.computationTimeoutShort,
        title: copy.computationTimeoutTitle(confidence.reason),
      };
    case 'refit_locked':
      return {
        disposition,
        colorTone,
        intervalLabel: null,
        shortLabel: copy.refitLockedShort,
        title: copy.refitLockedTitle(confidence.reason),
      };
    case 'delayed':
      return {
        disposition,
        colorTone,
        intervalLabel: null,
        shortLabel: copy.delayedShort,
        title: copy.delayedTitle(confidence.reason),
      };
    default:
      return {
        disposition,
        colorTone,
        intervalLabel: null,
        shortLabel: copy.unavailableOtherShort,
        title: copy.unavailableOtherTitle(confidence.reason),
      };
  }
}
