import { claimSourceLabel, commerceSourceLabel, formatClaimDifferenceDisplay, formatClaimTimeUtcDate } from './claimsLedgerDisplay';
import { formatMoneyMinorDisplay } from '../lib/money';
import type { DiscrepancyClass } from '../ledger/types';
import type {
  ClaimDetailDTO,
  ClaimEventMatchStatus,
  ClaimEvidencePhase,
  ClaimEvidenceStep,
  ClaimExecutiveVerdict,
} from '../detail/types';
import { campaignClassLabel, commerceRailLabel } from './claimsLedgerDisplay';

const ATTRIBUTION_MODEL_LABELS: Record<string, string> = {
  'first-touch': 'first-touch',
  'last-touch': 'last-touch',
  linear: 'even-split',
  'time-decay': 'time-weighted',
  last_touch: 'last-touch',
  first_touch: 'first-touch',
  time_decay: 'time-weighted',
};

export function formatShortClaimRef(claimRef: string): string {
  const segment = claimRef.split('_').pop() ?? claimRef;
  return segment.length > 4 ? segment.slice(-4) : segment;
}

export function formatClaimDetailTitle(claimSource: string, claimRef: string): string {
  const platform = claimSourceLabel(claimSource);
  const shortRef = formatShortClaimRef(claimRef);
  return `${platform} Claim #${shortRef}`;
}

export function attributionModelLabel(model: string): string {
  return ATTRIBUTION_MODEL_LABELS[model] ?? model.replace(/_/g, ' ');
}

export function resolveClaimExecutiveVerdict(data: Pick<
  ClaimDetailDTO,
  'verificationStatus' | 'discrepancyClass'
>): ClaimExecutiveVerdict {
  if (data.verificationStatus === 'unverified') return 'unverified';
  if (
    data.verificationStatus === 'verified' &&
    data.discrepancyClass === 'within_tolerance'
  ) {
    return 'verified';
  }
  return 'discrepancy';
}

export function claimEventMatchLabel(status: ClaimEventMatchStatus): string {
  return status === 'matched' ? 'Confirmed' : 'No receipt';
}

/**
 * Display hygiene for event labels: strip redundant "Ads Ad Set" after a platform
 * name (claim page already identifies the platform).
 */
export function formatClaimEventLabel(label: string): string {
  return label
    .replace(/\bAds\s+Ad\s+Set\b/gi, 'Ad set')
    .replace(/\bAd Set\b/g, 'Ad set');
}

export function differenceSeverityTone(
  discrepancyClass: DiscrepancyClass,
  rateBps: number,
): 'success' | 'warning' | 'error' {
  if (discrepancyClass === 'material' || Math.abs(rateBps) > 1000) return 'error';
  if (discrepancyClass === 'flagged' || Math.abs(rateBps) > 500) return 'error';
  if (discrepancyClass === 'within_tolerance') return 'success';
  return 'warning';
}

export function buildVerifiedNarrative(
  commerceSource: string,
  attributionModel: string,
  orderRef?: string,
): string {
  const commerce = commerceSourceLabel(commerceSource);
  const model = attributionModelLabel(attributionModel);
  const order = orderRef ? ` (Order ${orderRef})` : '';
  return `This claim matches the deterministic commerce evidence from ${commerce}${order} using the ${model} attribution model.`;
}

export function formatClaimEventDate(iso: string): string {
  return formatClaimTimeUtcDate(iso) ?? iso;
}

export function formatChannelLabel(channelKey: string): string {
  if (channelKey in { paid_search: 1, paid_social: 1, creator: 1, branded: 1, affiliate: 1 }) {
    return campaignClassLabel(channelKey);
  }
  return commerceRailLabel(channelKey);
}

/** Short platform name for CFO synthesis (Meta, not Meta Ads). */
export function claimSourceShortLabel(claimSource: string): string {
  const SHORT: Record<string, string> = {
    meta_ads: 'Meta',
    google_ads: 'Google',
    tiktok_ads: 'TikTok',
    linkedin_ads: 'LinkedIn',
  };
  return SHORT[claimSource] ?? claimSourceLabel(claimSource).replace(/\s+Ads$/i, '');
}

export function formatPaidPlatformClassLabel(platform: string, campaignClass: string): string {
  return `${claimSourceShortLabel(platform)} · ${campaignClassLabel(campaignClass)}`;
}

export function formatShareOfVerified(amountMinor: bigint, paidTotalMinor: bigint): string {
  if (paidTotalMinor <= 0n) return '0%';
  const pct = Number((amountMinor * 1000n) / paidTotalMinor) / 10;
  return Number.isInteger(pct) ? `${pct}%` : `${pct.toFixed(1)}%`;
}

export const CLAIM_EVIDENCE_PHASE_ORDER: readonly ClaimEvidencePhase[] = [
  'intake',
  'verification',
  'record',
];

export function formatEvidenceStepDateLine(iso: string): string | null {
  return formatClaimTimeUtcDate(iso);
}

export function formatEvidenceStepTimeLine(iso: string): string | null {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return null;
  }

  return new Intl.DateTimeFormat('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    second: '2-digit',
    timeZone: 'UTC',
    timeZoneName: 'short',
  }).format(date);
}

export function shouldShowEvidenceStepDate(
  steps: ClaimEvidenceStep[],
  index: number,
): boolean {
  if (index === 0) return true;
  const current = formatEvidenceStepDateLine(steps[index].timestamp);
  const previous = formatEvidenceStepDateLine(steps[index - 1].timestamp);
  return current !== previous;
}

export function groupClaimEvidenceStepsByPhase(steps: ClaimEvidenceStep[]): Array<{
  phase: ClaimEvidencePhase;
  steps: Array<{ step: ClaimEvidenceStep; index: number }>;
}> {
  const groups = new Map<ClaimEvidencePhase, Array<{ step: ClaimEvidenceStep; index: number }>>();

  steps.forEach((step, index) => {
    const phase = step.phase ?? 'verification';
    const bucket = groups.get(phase) ?? [];
    bucket.push({ step, index });
    groups.set(phase, bucket);
  });

  return CLAIM_EVIDENCE_PHASE_ORDER.filter((phase) => groups.has(phase)).map((phase) => ({
    phase,
    steps: groups.get(phase)!,
  }));
}

export {
  claimSourceLabel,
  commerceSourceLabel,
  formatClaimDifferenceDisplay,
  formatMoneyMinorDisplay,
};
