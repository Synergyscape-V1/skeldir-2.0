import type { TrustEnvelopeIndexRowDTO } from '../ledger/types';
import type { PolicyAuthorityState } from '../lib/types';
import { discrepancyRateTier } from './channelTrustDisplay';
import { buildClaimTrustDrawerHref } from '../trustIndex/envelopeClaimRouting';
import type {
  RecentEnvelopeDrillFocus,
  RecentEnvelopeMatchVerdict,
  RecentEnvelopeRow,
  RecentEnvelopeTrustSignal,
} from './types';
import {
  DEFAULT_RECENT_SIGNAL_WINDOW,
  MAX_RECENT_ENVELOPES,
  type RecentSignalWindow,
  recentSignalWindowMs,
} from './recentEnvelopesConstants';

export function mapTrustIndexRowToRecentEnvelope(row: TrustEnvelopeIndexRowDTO): RecentEnvelopeRow {
  return {
    envelopeId: row.envelopeId,
    // Subject reference is the primary findability key — never substitute label/detail.
    subjectRef: row.subjectRef,
    matchVerdict: normalizeMatchVerdict(row.matchVerdict),
    verifiedRevenueMinor: row.verifiedRevenueMinor,
    currencyCode: row.currencyCode,
    discrepancyRateBps: row.discrepancyRateBps,
    policyAuthority: row.policyAuthority,
    trustSignal: resolveTrustSignal(row),
    createdAt: row.generationTimestamp || row.claimTime,
    auditReference: row.auditReference,
  };
}

function normalizeMatchVerdict(
  verdict: TrustEnvelopeIndexRowDTO['matchVerdict'],
): RecentEnvelopeMatchVerdict {
  if (verdict === 'matched_confirmed') return 'matched_confirmed';
  if (verdict === 'unmatched') return 'unmatched';
  return 'adjusted';
}

function resolveTrustSignal(row: TrustEnvelopeIndexRowDTO): RecentEnvelopeTrustSignal {
  if (row.benchmark?.sourceTransition) return 'estimator_transition';
  if (row.confidence?.status === 'unavailable') return 'confidence_unavailable';
  return null;
}

export function sortRecentEnvelopesChronological(rows: RecentEnvelopeRow[]): RecentEnvelopeRow[] {
  return [...rows].sort(
    (a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt) || a.envelopeId.localeCompare(b.envelopeId),
  );
}

export function filterRecentEnvelopesBySignalWindow(
  rows: RecentEnvelopeRow[],
  window: RecentSignalWindow = DEFAULT_RECENT_SIGNAL_WINDOW,
  referenceMs: number = Date.now(),
): RecentEnvelopeRow[] {
  const cutoff = referenceMs - recentSignalWindowMs(window);
  return rows.filter((row) => {
    const created = Date.parse(row.createdAt);
    return Number.isFinite(created) && created >= cutoff;
  });
}

export function buildRecentEnvelopeFeed(
  rows: RecentEnvelopeRow[],
  options?: { window?: RecentSignalWindow; referenceMs?: number },
): RecentEnvelopeRow[] {
  const window = options?.window ?? DEFAULT_RECENT_SIGNAL_WINDOW;
  const filtered = filterRecentEnvelopesBySignalWindow(rows, window, options?.referenceMs);
  return sortRecentEnvelopesChronological(filtered).slice(0, MAX_RECENT_ENVELOPES);
}

export function recentEnvelopeRowBand(
  discrepancyRateBps: number | null | undefined,
): 'amber' | 'red' | 'neutral' {
  const tier = discrepancyRateTier(discrepancyRateBps);
  if (tier === 'amber') return 'amber';
  if (tier === 'red') return 'red';
  return 'neutral';
}

export function matchVerdictLabel(verdict: RecentEnvelopeMatchVerdict): string {
  switch (verdict) {
    case 'matched_confirmed':
      return 'matched_confirmed';
    case 'adjusted':
      return 'adjusted';
    case 'unmatched':
      return 'unmatched';
    default:
      return 'invalid_verdict';
  }
}

export function trustSignalLabel(signal: RecentEnvelopeTrustSignal): string | null {
  switch (signal) {
    case 'confidence_unavailable':
      return 'Unavailable';
    case 'estimator_transition':
      return 'Estimator Transition';
    default:
      return null;
  }
}

export function resolveRecentEnvelopeDrillDown(row: RecentEnvelopeRow): {
  href: string;
  focus: RecentEnvelopeDrillFocus | null;
} {
  const band = recentEnvelopeRowBand(row.discrepancyRateBps);

  if (
    band === 'amber' ||
    band === 'red' ||
    row.matchVerdict === 'adjusted' ||
    row.matchVerdict === 'unmatched'
  ) {
    return { href: buildClaimTrustDrawerHref(row.envelopeId, 'evidence'), focus: 'evidence' };
  }
  if (row.policyAuthority === 'approval_required') {
    return { href: buildClaimTrustDrawerHref(row.envelopeId, 'policy'), focus: 'policy' };
  }
  if (row.trustSignal === 'estimator_transition') {
    return { href: buildClaimTrustDrawerHref(row.envelopeId, 'confidence'), focus: 'confidence' };
  }
  return { href: buildClaimTrustDrawerHref(row.envelopeId), focus: null };
}

export function isPolicyAuthorityState(value: string): value is PolicyAuthorityState {
  return (
    value === 'blocked' ||
    value === 'simulation_only' ||
    value === 'proposal_required' ||
    value === 'approval_required' ||
    value === 'auto_executable_within_policy'
  );
}
