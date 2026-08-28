import type { RecentEnvelopeRow } from './types';

function minutesAgo(minutes: number): string {
  return new Date(Date.now() - minutes * 60_000).toISOString();
}

function daysAgo(days: number): string {
  return new Date(Date.now() - days * 24 * 60 * 60_000).toISOString();
}

/**
 * Canonical Recent TrustEnvelopes feed — intentionally unsorted here;
 * client applies chronological sort + active signal window (never severity).
 */
export const COMMAND_CENTER_RECENT_ENVELOPES: RecentEnvelopeRow[] = [
  {
    envelopeId: 'env_0101',
    subjectRef: 'ord_8f9a2c1d4e7b3a61',
    matchVerdict: 'matched_confirmed',
    verifiedRevenueMinor: 428_460_00n,
    currencyCode: 'USD',
    discrepancyRateBps: 80,
    policyAuthority: 'blocked',
    trustSignal: null,
    createdAt: minutesAgo(6),
    auditReference: 'audit_01J94Z8K2M1946E',
  },
  {
    envelopeId: 'env_0102',
    subjectRef: 'ord_2b7c9f1e8a4d6c30',
    matchVerdict: 'adjusted',
    verifiedRevenueMinor: 256_140_00n,
    currencyCode: 'USD',
    discrepancyRateBps: 460,
    policyAuthority: 'approval_required',
    trustSignal: null,
    createdAt: minutesAgo(22),
    auditReference: 'audit_01J94Z9P3N2847F',
  },
  {
    envelopeId: 'env_0103',
    subjectRef: 'ord_6d1a0e5f3c8b2h71',
    matchVerdict: 'unmatched',
    verifiedRevenueMinor: 184_920_00n,
    currencyCode: 'USD',
    discrepancyRateBps: 1240,
    policyAuthority: 'blocked',
    trustSignal: null,
    createdAt: minutesAgo(47),
    auditReference: 'audit_01J94ZA4Q5O3958G',
  },
  {
    envelopeId: 'env_0104',
    subjectRef: 'ord_9e4f2a8c1d7b5e20',
    matchVerdict: 'matched_confirmed',
    verifiedRevenueMinor: 512_880_00n,
    currencyCode: 'USD',
    discrepancyRateBps: 40,
    policyAuthority: 'simulation_only',
    trustSignal: 'confidence_unavailable',
    createdAt: minutesAgo(190),
    auditReference: 'audit_01J94ZB6R7P4069H',
  },
  {
    envelopeId: 'env_0105',
    subjectRef: 'ord_1c5e7a9b2f4d8h63',
    matchVerdict: 'matched_confirmed',
    verifiedRevenueMinor: 312_400_00n,
    currencyCode: 'USD',
    discrepancyRateBps: 120,
    policyAuthority: 'blocked',
    trustSignal: 'estimator_transition',
    createdAt: minutesAgo(520),
    auditReference: 'audit_01J94ZC8S9Q5180I',
  },
  {
    envelopeId: 'env_0106',
    subjectRef: 'ord_3f8a1c6e9b2d4g95',
    matchVerdict: 'adjusted',
    verifiedRevenueMinor: 98_760_00n,
    currencyCode: 'USD',
    discrepancyRateBps: 320,
    policyAuthority: 'proposal_required',
    trustSignal: null,
    createdAt: minutesAgo(980),
    auditReference: 'audit_01J94ZD0T1R6291J',
  },
  {
    envelopeId: 'env_0107',
    subjectRef: 'ord_5h2g8j1k4m7n0p32',
    matchVerdict: 'matched_confirmed',
    verifiedRevenueMinor: 67_500_00n,
    currencyCode: 'USD',
    discrepancyRateBps: 60,
    policyAuthority: 'blocked',
    trustSignal: null,
    createdAt: minutesAgo(1380),
    auditReference: 'audit_01J94ZE2U3S7402K',
  },
  {
    envelopeId: 'env_0108',
    subjectRef: 'ord_7k9m2n5p8q1r4s67',
    matchVerdict: 'matched_confirmed',
    verifiedRevenueMinor: 145_200_00n,
    currencyCode: 'USD',
    discrepancyRateBps: 90,
    policyAuthority: 'blocked',
    trustSignal: null,
    createdAt: daysAgo(5),
    auditReference: 'audit_01J94ZF4V5T8513L',
  },
];
