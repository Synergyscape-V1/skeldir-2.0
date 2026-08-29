import type { BayesianStatusKey } from '../commandCenter/types';
import { formatMoneyMinorDisplay } from '../lib/money';
import type { ConfidenceShape, DiscrepancyClass } from '../ledger/types';
import {
  CAMPAIGN_CLASS_LABELS,
  CLAIM_SOURCE_LABELS,
  COMMERCE_RAIL_LABELS,
  COMMERCE_TRUTH_SOURCE_LABELS,
} from './claimsFilterConfig';

export function claimSourceLabel(claimSource: string): string {
  return CLAIM_SOURCE_LABELS[claimSource] ?? claimSource.replace(/_/g, ' ');
}

export function campaignClassLabel(campaignClass: string): string {
  return CAMPAIGN_CLASS_LABELS[campaignClass] ?? campaignClass.replace(/_/g, ' ');
}

export function commerceRailLabel(commerceRail: string): string {
  return COMMERCE_RAIL_LABELS[commerceRail] ?? commerceRail.replace(/_/g, ' ');
}

export function commerceSourceLabel(commerceSource: string): string {
  return COMMERCE_TRUTH_SOURCE_LABELS[commerceSource] ?? commerceSource.replace(/_/g, ' ');
}

export function formatClaimTimeUtcDate(iso: string): string | null {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return null;
  }

  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(date);
}

export function formatClaimTimeUtcLines(iso: string): { dateLine: string; timeLine: string } | null {
  const dateLabel = formatClaimTimeUtcDate(iso);
  if (!dateLabel) {
    return null;
  }

  const date = new Date(iso);
  const timeLine = new Intl.DateTimeFormat('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    timeZone: 'UTC',
    timeZoneName: 'short',
  }).format(date);

  return { dateLine: `${dateLabel},`, timeLine };
}

export function differenceSeverityClass(discrepancyClass: DiscrepancyClass): 'neutral' | 'success' | 'warning' | 'error' {
  if (discrepancyClass === 'within_tolerance') return 'success';
  if (discrepancyClass === 'flagged') return 'warning';
  if (discrepancyClass === 'material') return 'error';
  return 'neutral';
}

export function formatClaimDifferenceDisplay(
  claimedMinor: bigint,
  verifiedMinor: bigint,
  discrepancyRateBps: number,
  currencyCode: string,
): { amount: string; percent: string; combined: string } {
  const differenceMinor = verifiedMinor - claimedMinor;
  const amount = formatMoneyMinorDisplay(differenceMinor, currencyCode);
  const pctVal = (Math.abs(discrepancyRateBps) / 100).toFixed(2);
  let percent: string;
  if (differenceMinor === 0n) {
    percent = '0.00% of claimed revenue';
  } else {
    percent = `${pctVal}% of claimed revenue`;
  }
  return {
    amount,
    percent,
    combined: `${amount} · ${percent}`,
  };
}

export function verifiedAuthorityHint(verifiedRevenueMinor: bigint, claimedRevenueMinor: bigint): string {
  return verifiedRevenueMinor === claimedRevenueMinor ? 'Deterministic' : 'Artifact-backed';
}

export function confidenceToBayesianStatus(confidence: ConfidenceShape): BayesianStatusKey {
  if (confidence.status === 'unavailable') return 'unavailable';
  if (confidence.status === 'delayed') return 'delayed';
  const qualitative = confidence.qualitativeState?.toLowerCase() ?? '';
  if (qualitative.includes('moderate') || qualitative.includes('low')) {
    return 'low_confidence';
  }
  return 'healthy';
}
