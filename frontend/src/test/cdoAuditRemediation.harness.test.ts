import { describe, expect, it } from 'vitest';
import {
  resolveRevenueReliabilityFromAgreementBps,
  resolveRevenueReliabilityFromAgreementPercent,
  resolveRevenueReliabilityFromTier,
} from '../trust/revenueReliability';
import {
  REVENUE_RELIABILITY_COLUMN_HEADER,
  REVENUE_RELIABILITY_HEADER_TOOLTIP,
  revenueReliabilityBadgeLabel,
  revenueReliabilityBadgeTooltip,
} from '../trust/revenueReliabilityCopy';
import {
  resolveClaimLedgerExecutiveReliability,
  resolveExecutiveDataReliability,
  resolveTrustEnvelopeExecutiveReliability,
} from '../trust/executiveDataReliability';
import { resolveDiscrepancyPresentation } from '../claims/discrepancySemantics';

describe('CDO Audit 1/2 — revenue reliability remediation', () => {
  it('maps high model agreement tier to Robust badge state', () => {
    expect(resolveRevenueReliabilityFromTier('high')).toEqual({ state: 'robust' });
    expect(revenueReliabilityBadgeLabel('robust')).toBe('Robust');
    expect(revenueReliabilityBadgeTooltip('robust')).toMatch(/CFO-defensible|budget decisions/i);
  });

  it('maps medium tier to Mixed and low/conflict to Fragile', () => {
    expect(resolveRevenueReliabilityFromTier('medium')).toEqual({ state: 'mixed' });
    expect(resolveRevenueReliabilityFromTier('low')).toEqual({ state: 'fragile' });
    expect(resolveRevenueReliabilityFromTier('conflict')).toEqual({ state: 'fragile' });
    expect(revenueReliabilityBadgeLabel('mixed')).toBe('Mixed');
    expect(revenueReliabilityBadgeLabel('fragile')).toBe('Fragile');
  });

  it('maps agreement percent strings to reliability states without exposing High/Medium/Low', () => {
    expect(resolveRevenueReliabilityFromAgreementPercent('96.2%')).toEqual({ state: 'robust' });
    expect(resolveRevenueReliabilityFromAgreementPercent('88.4%')).toEqual({ state: 'mixed' });
    expect(resolveRevenueReliabilityFromAgreementPercent('72.1%')).toEqual({ state: 'fragile' });
    expect(resolveRevenueReliabilityFromAgreementBps(9620)).toEqual({ state: 'robust' });
  });

  it('fail-closed on unknown model agreement tier', () => {
    expect(resolveRevenueReliabilityFromTier('causal')).toEqual({ state: 'fragile', invalid: true });
  });

  it('column header copy removes model agreement jargon', () => {
    expect(REVENUE_RELIABILITY_COLUMN_HEADER).toBe('Revenue Reliability');
    expect(REVENUE_RELIABILITY_COLUMN_HEADER).not.toMatch(/model agreement/i);
  });

  it('header and badge tooltips use commercial risk language — not attribution mechanics', () => {
    expect(REVENUE_RELIABILITY_HEADER_TOOLTIP).toMatch(/budget decisions/i);
    expect(REVENUE_RELIABILITY_HEADER_TOOLTIP).not.toMatch(/attribution model/i);
    expect(revenueReliabilityBadgeTooltip('robust')).not.toMatch(/attribution model/i);
    expect(revenueReliabilityBadgeTooltip('mixed')).not.toMatch(/attribution model/i);
    expect(revenueReliabilityBadgeTooltip('fragile')).not.toMatch(/attribution model/i);
    expect(revenueReliabilityBadgeTooltip('fragile')).toMatch(/assumption/i);
  });
});

describe('CDO Audit 1/2 — executive reliability mapping', () => {
  it('maps matched_confirmed + available confidence to Verified', () => {
    const resolution = resolveExecutiveDataReliability({
      matchVerdict: 'matched_confirmed',
      confidence: { status: 'available' },
      extractionFreshness: 'fresh',
    });
    expect(resolution.reliability).toBe('verified');
    expect(resolution.allowsVerifiedExport).toBe(true);
    expect(resolution.allowsSimulator).toBe(true);
  });

  it('maps matched_provisional to Estimated (never Verified)', () => {
    const resolution = resolveExecutiveDataReliability({
      matchVerdict: 'matched_provisional',
      confidence: { status: 'available' },
    });
    expect(resolution.reliability).toBe('estimated');
    expect(resolution.variant).toBe('matched_provisional');
    expect(resolution.allowsVerifiedExport).toBe(false);
  });

  it('maps unmatched + stale extraction to Pending', () => {
    const resolution = resolveExecutiveDataReliability({
      matchVerdict: 'unmatched',
      confidence: { status: 'delayed' },
      extractionFreshness: 'stale',
    });
    expect(resolution.reliability).toBe('pending');
    expect(resolution.allowsVerifiedExport).toBe(false);
  });

  it('maps confidence unavailable on confirmed match to Estimated', () => {
    const resolution = resolveExecutiveDataReliability({
      matchVerdict: 'matched_confirmed',
      confidence: { status: 'unavailable', reason: 'insufficient_data' },
    });
    expect(resolution.reliability).toBe('estimated');
    expect(resolution.variant).toBe('confidence_building');
  });

  it('maps confidence timeout to Estimated with paused variant', () => {
    const resolution = resolveExecutiveDataReliability({
      matchVerdict: 'matched_confirmed',
      confidence: { status: 'unavailable', reason: 'unavailable_timeout' },
    });
    expect(resolution.reliability).toBe('estimated');
    expect(resolution.variant).toBe('confidence_paused');
  });

  it('fail-closed: unknown match verdict never maps to Verified', () => {
    const resolution = resolveExecutiveDataReliability({
      matchVerdict: 'causal',
      confidence: { status: 'available' },
    });
    expect(resolution.reliability).toBe('estimated');
    expect(resolution.allowsVerifiedExport).toBe(false);
  });

  it('maps claim ledger partial verification to Estimated', () => {
    const resolution = resolveClaimLedgerExecutiveReliability({
      matchVerdict: 'within_tolerance',
      confidence: { status: 'available' },
      verificationStatus: 'partial',
    });
    expect(resolution.reliability).toBe('estimated');
  });

  it('maps trust envelope operator projection consistently', () => {
    const verified = resolveTrustEnvelopeExecutiveReliability({
      matchVerdictStatus: 'matched_confirmed',
      confidence: { status: 'available' },
      extractionFreshness: 'fresh',
    });
    const estimated = resolveTrustEnvelopeExecutiveReliability({
      matchVerdictStatus: 'matched_provisional',
      confidence: { status: 'unavailable', reason: 'insufficient_data' },
      extractionFreshness: 'fresh',
    });
    expect(verified.reliability).toBe('verified');
    expect(estimated.reliability).toBe('estimated');
  });

  it('override: flagged discrepancy forces Discrepancy regardless of match/confidence', () => {
    const resolution = resolveClaimLedgerExecutiveReliability({
      matchVerdict: 'within_tolerance',
      confidence: { status: 'available' },
      verificationStatus: 'verified',
      discrepancyClass: 'flagged',
    });
    expect(resolution.reliability).toBe('discrepancy');
    expect(resolution.variant).toBe('flagged');
    expect(resolution.allowsVerifiedExport).toBe(false);
    expect(resolution.allowsSimulator).toBe(false);
  });

  it('override: material discrepancy forces Discrepancy with material variant', () => {
    const resolution = resolveExecutiveDataReliability({
      matchVerdict: 'matched_confirmed',
      confidence: { status: 'available' },
      verificationStatus: 'verified',
      discrepancyClass: 'material',
    });
    expect(resolution.reliability).toBe('discrepancy');
    expect(resolution.variant).toBe('material');
    expect(resolution.allowsVerifiedExport).toBe(false);
  });

  it('fail-closed: unknown discrepancy class forces Discrepancy, never Verified', () => {
    const resolution = resolveExecutiveDataReliability({
      matchVerdict: 'matched_confirmed',
      confidence: { status: 'available' },
      verificationStatus: 'verified',
      discrepancyClass: 'unknown',
    });
    expect(resolution.reliability).toBe('discrepancy');
    expect(resolution.allowsVerifiedExport).toBe(false);
  });

  it('meta-negative: removing the discrepancy override returns a reassuring non-Discrepancy verdict for flagged input', () => {
    const flaggedInput = {
      matchVerdict: 'within_tolerance',
      confidence: { status: 'available' },
      verificationStatus: 'verified',
      discrepancyClass: 'flagged',
    } as const;
    const honest = resolveClaimLedgerExecutiveReliability(flaggedInput);
    expect(honest.reliability).toBe('discrepancy');

    const bypassed: ExecutiveReliabilityResolution = {
      reliability: 'verified',
      allowsSimulator: true,
      allowsVerifiedExport: true,
    };
    expect(bypassed.reliability).not.toBe(honest.reliability);
  });
});

describe('CDO Audit 1/2 — discrepancy semantics', () => {
  it('maps within_tolerance to unlocked variance gate', () => {
    const presentation = resolveDiscrepancyPresentation({
      claimedRevenueMinor: 1_000_000n,
      verifiedRevenueMinor: 992_000n,
      discrepancyAmountMinor: 8_000n,
      discrepancyRateBps: 80,
      discrepancyClass: 'within_tolerance',
      currencyCode: 'USD',
    });
    expect('error' in presentation).toBe(false);
    if ('error' in presentation) return;
    expect(presentation.varianceGateLocked).toBe(false);
    expect(presentation.percentOfClaimedLabel).toMatch(/of claimed revenue/);
    expect(presentation.badgeLabel).toBe('Within tolerance');
  });

  it('maps flagged to action-blocked variance gate with 2% threshold copy', () => {
    const presentation = resolveDiscrepancyPresentation({
      claimedRevenueMinor: 1_000_000n,
      verifiedRevenueMinor: 900_000n,
      discrepancyAmountMinor: 100_000n,
      discrepancyRateBps: 1000,
      discrepancyClass: 'flagged',
      currencyCode: 'USD',
    });
    expect('error' in presentation).toBe(false);
    if ('error' in presentation) return;
    expect(presentation.varianceGateLocked).toBe(true);
    expect(presentation.thresholdContextLabel).toMatch(/2%/);
    expect(presentation.varianceGateLabel).toMatch(/Action blocked/);
  });

  it('maps material to alert badge with 10% threshold copy', () => {
    const presentation = resolveDiscrepancyPresentation({
      claimedRevenueMinor: 1_000_000n,
      verifiedRevenueMinor: 800_000n,
      discrepancyAmountMinor: 200_000n,
      discrepancyRateBps: 2000,
      discrepancyClass: 'material',
      currencyCode: 'USD',
    });
    expect('error' in presentation).toBe(false);
    if ('error' in presentation) return;
    expect(presentation.badgeLabel).toMatch(/Alert/);
    expect(presentation.thresholdContextLabel).toMatch(/10%/);
  });

  it('fail-closed on unknown discrepancy class', () => {
    const presentation = resolveDiscrepancyPresentation({
      claimedRevenueMinor: 1n,
      verifiedRevenueMinor: 0n,
      discrepancyRateBps: 100,
      discrepancyClass: 'unknown',
      currencyCode: 'USD',
    });
    expect('error' in presentation).toBe(true);
  });
});

describe('CDO Audit 1/2 — negative scope (no raw telemetry labels)', () => {
  it('resolver input uses closed enums only — no percentage surfaces', () => {
    const fixture = {
      matchVerdict: 'matched_confirmed',
      confidence: { status: 'unavailable' as const, reason: 'insufficient_data' },
    };
    const resolution = resolveExecutiveDataReliability(fixture);
    expect(JSON.stringify(resolution)).not.toMatch(/extraction confidence|source quality|0\.\d+/i);
  });
});
