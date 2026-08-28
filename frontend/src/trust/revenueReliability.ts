import type { ModelAgreementTier } from '../commandCenter/types';

export type RevenueReliabilityState = 'robust' | 'mixed' | 'fragile';

export interface RevenueReliabilityResolution {
  state: RevenueReliabilityState;
  invalid?: boolean;
}

const AGREEMENT_BPS_ROBUST_MIN = 9000;
const AGREEMENT_BPS_MIXED_MIN = 8000;

export function parseModelAgreementPercentToBps(value: string): number {
  const match = value.match(/(\d+)(?:\.(\d+))?/);
  if (!match) return 0;
  const fractional = (match[2] ?? '0').padEnd(2, '0').slice(0, 2);
  return Number.parseInt(match[1], 10) * 100 + Number.parseInt(fractional, 10);
}

export function resolveRevenueReliabilityFromAgreementBps(bps: number): RevenueReliabilityResolution {
  if (bps >= AGREEMENT_BPS_ROBUST_MIN) {
    return { state: 'robust' };
  }
  if (bps >= AGREEMENT_BPS_MIXED_MIN) {
    return { state: 'mixed' };
  }
  return { state: 'fragile' };
}

export function resolveRevenueReliabilityFromAgreementPercent(
  value: string,
): RevenueReliabilityResolution {
  return resolveRevenueReliabilityFromAgreementBps(parseModelAgreementPercentToBps(value));
}

export function resolveRevenueReliabilityFromTier(
  tier: ModelAgreementTier | string,
): RevenueReliabilityResolution {
  switch (tier) {
    case 'high':
      return { state: 'robust' };
    case 'medium':
      return { state: 'mixed' };
    case 'low':
    case 'conflict':
      return { state: 'fragile' };
    default:
      return { state: 'fragile', invalid: true };
  }
}
