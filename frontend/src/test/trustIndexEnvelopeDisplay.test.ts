import { describe, expect, it } from 'vitest';
import type { TrustEnvelopeIndexRowDTO } from '../ledger/types';
import { sortTrustEnvelopeIndexRows } from '../trustIndex/trustIndexEnvelopeDisplay';

function row(partial: Partial<TrustEnvelopeIndexRowDTO> & { envelopeId: string }): TrustEnvelopeIndexRowDTO {
  return {
    subjectRef: 'ref',
    subjectLabel: 'Revenue Claim',
    subjectDetail: 'detail',
    claimTime: '2026-01-01T12:00:00.000Z',
    claimSource: 'meta_ads',
    claimedRevenueMinor: 1100n,
    verifiedRevenueMinor: 1000n,
    currencyCode: 'USD',
    discrepancyAmountMinor: 100n,
    discrepancyRateBps: 1000,
    discrepancyClass: 'material',
    matchVerdict: 'unmatched',
    verificationStatus: 'verified',
    revenueAuthority: 'deterministic',
    attributionModel: 'Time-decay model',
    attributionAuthority: 'deterministic',
    confidence: { status: 'available', authority: 'probabilistic' },
    benchmark: { status: 'unavailable', reason: 'Insufficient cross-tenant signal.' },
    auditRecordStatus: 'linked',
    policyAuthority: 'blocked',
    channelSource: 'meta_ads',
    auditReference: 'aud_1',
    generationTimestamp: '2026-01-01T12:00:00.000Z',
    status: 'active',
    futureDetailAffordance: 'detail_blocked_level_8',
    ...partial,
  };
}

describe('sortTrustEnvelopeIndexRows', () => {
  it('sorts policy authority before discrepancy before claim time', () => {
    const rows = sortTrustEnvelopeIndexRows([
      row({
        envelopeId: 'env_low',
        policyAuthority: 'auto_executable_within_policy',
        discrepancyClass: 'material',
        discrepancyRateBps: 2000,
        claimTime: '2026-01-05T12:00:00.000Z',
      }),
      row({
        envelopeId: 'env_high',
        policyAuthority: 'approval_required',
        discrepancyClass: 'within_tolerance',
        discrepancyRateBps: 50,
        claimTime: '2026-01-01T12:00:00.000Z',
      }),
      row({
        envelopeId: 'env_mid',
        policyAuthority: 'approval_required',
        discrepancyClass: 'material',
        discrepancyRateBps: 1500,
        claimTime: '2026-01-03T12:00:00.000Z',
      }),
    ]);

    expect(rows.map((entry) => entry.envelopeId)).toEqual(['env_mid', 'env_high', 'env_low']);
  });
});
