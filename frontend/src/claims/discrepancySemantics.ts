import type { DiscrepancyStatus } from '../commandCenter/types';
import { formatMoneyMinorDisplay } from '../lib/money';
import type { DiscrepancyClass } from '../ledger/types';

/** B2.3 match-engine discrepancy bands (basis points). */
export const DISCREPANCY_THRESHOLD_BPS = {
  withinMax: 200,
  flaggedMax: 1000,
} as const;

export interface DiscrepancyPresentationInput {
  claimedRevenueMinor: bigint;
  verifiedRevenueMinor: bigint;
  discrepancyAmountMinor?: bigint;
  discrepancyRateBps: number;
  discrepancyClass: DiscrepancyClass;
  currencyCode: string;
}

export interface DiscrepancyPresentation {
  amountDisplay: string;
  /** Compact table percent, e.g. "14.00%". */
  compactPercentLabel: string;
  /** Full relative phrasing for hero / a11y, e.g. "14.00% of claimed revenue". */
  percentOfClaimedLabel: string;
  badgeStatus: DiscrepancyStatus;
  badgeLabel: string;
  /** Short status for dense table cells. */
  compactBadgeLabel: string;
  thresholdContextLabel: string;
  tooltip: string;
  severityTone: 'success' | 'warning' | 'error' | 'neutral';
  varianceGateLocked: boolean;
  varianceGateLabel: string;
  varianceGateTone: 'info' | 'warning';
}

export function discrepancyClassToStatus(discrepancyClass: DiscrepancyClass): DiscrepancyStatus {
  if (discrepancyClass === 'within_tolerance') return 'within_tolerance';
  if (discrepancyClass === 'flagged') return 'flagged';
  if (discrepancyClass === 'material') return 'rejected';
  return 'unavailable';
}

function formatCompactPercent(discrepancyRateBps: number, differenceMinor: bigint): string {
  if (differenceMinor === 0n) return '0.00% of claim';
  return `${(Math.abs(discrepancyRateBps) / 100).toFixed(2)}% of claim`;
}

function formatPercentOfClaimed(discrepancyRateBps: number, differenceMinor: bigint): string {
  if (differenceMinor === 0n) return '0.00% of claimed revenue';
  return `${(Math.abs(discrepancyRateBps) / 100).toFixed(2)}% of claimed revenue`;
}

function thresholdPercentLabel(bps: number): string {
  return `${(bps / 100).toFixed(0)}%`;
}

export function resolveDiscrepancyPresentation(
  input: DiscrepancyPresentationInput,
): DiscrepancyPresentation | { error: string } {
  const { discrepancyClass } = input;

  if (discrepancyClass === 'unknown') {
    return { error: 'Unknown discrepancy class — cannot render variance without backend classification.' };
  }

  const differenceMinor =
    input.discrepancyAmountMinor ?? input.verifiedRevenueMinor - input.claimedRevenueMinor;
  const amountDisplay = formatMoneyMinorDisplay(differenceMinor, input.currencyCode);
  const compactPercentLabel = formatCompactPercent(input.discrepancyRateBps, differenceMinor);
  const percentOfClaimedLabel = formatPercentOfClaimed(input.discrepancyRateBps, differenceMinor);
  const badgeStatus = discrepancyClassToStatus(discrepancyClass);

  if (discrepancyClass === 'within_tolerance') {
    const withinLabel = thresholdPercentLabel(DISCREPANCY_THRESHOLD_BPS.withinMax);
    return {
      amountDisplay,
      compactPercentLabel,
      percentOfClaimedLabel,
      badgeStatus,
      badgeLabel: 'Within tolerance',
      compactBadgeLabel: 'Within tolerance',
      thresholdContextLabel: `Within ${withinLabel} acceptable variance`,
      tooltip: `${amountDisplay} · ${percentOfClaimedLabel}. Your organization accepts discrepancies up to ${withinLabel} without manual review.`,
      severityTone: 'success',
      varianceGateLocked: false,
      varianceGateLabel: `Within ${withinLabel} acceptable variance.`,
      varianceGateTone: 'info',
    };
  }

  if (discrepancyClass === 'flagged') {
    const flaggedLabel = thresholdPercentLabel(DISCREPANCY_THRESHOLD_BPS.withinMax);
    return {
      amountDisplay,
      compactPercentLabel,
      percentOfClaimedLabel,
      badgeStatus,
      badgeLabel: 'Flagged for review',
      compactBadgeLabel: 'Flagged',
      thresholdContextLabel: `Exceeds ${flaggedLabel} threshold`,
      tooltip: `${amountDisplay} · ${percentOfClaimedLabel}. Your organization flags discrepancies above ${flaggedLabel} for manual review.`,
      severityTone: 'warning',
      varianceGateLocked: true,
      varianceGateLabel: `Exceeds ${flaggedLabel} variance threshold. Action blocked.`,
      varianceGateTone: 'warning',
    };
  }

  const materialLabel = thresholdPercentLabel(DISCREPANCY_THRESHOLD_BPS.flaggedMax);
  return {
    amountDisplay,
    compactPercentLabel,
    percentOfClaimedLabel,
    badgeStatus,
    badgeLabel: 'Alert — exceeds threshold',
    compactBadgeLabel: 'Alert',
    thresholdContextLabel: `Exceeds ${materialLabel} threshold`,
    tooltip: `${amountDisplay} · ${percentOfClaimedLabel}. Your organization rejects discrepancies above ${materialLabel}.`,
    severityTone: 'error',
    varianceGateLocked: true,
    varianceGateLabel: `Exceeds ${materialLabel} variance threshold. Action blocked.`,
    varianceGateTone: 'warning',
  };
}
