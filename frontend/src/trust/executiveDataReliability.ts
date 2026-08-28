import type { ConfidenceShape, DiscrepancyClass } from '../ledger/types';
import type { ClaimDetailDTO } from '../detail/types';

export type ExecutiveDataReliability =
  | 'verified'
  | 'estimated'
  | 'pending'
  | 'unavailable'
  | 'discrepancy';

export type ExtractionFreshness = 'fresh' | 'stale' | 'failed';

export type ExecutiveReliabilityVariant =
  | 'matched_provisional'
  | 'confidence_building'
  | 'confidence_paused'
  | 'confidence_updating'
  | 'flagged'
  | 'material';

export type CanonicalMatchVerdict =
  | 'matched_confirmed'
  | 'matched_provisional'
  | 'adjusted'
  | 'unmatched'
  | 'pending'
  | 'failed';

export interface ExecutiveReliabilityInput {
  matchVerdict?: string | null;
  confidence?: Pick<ConfidenceShape, 'status' | 'reason'>;
  extractionFreshness?: ExtractionFreshness;
  verificationStatus?: ClaimDetailDTO['verificationStatus'];
  fallbackReason?: string | null;
  discrepancyClass?: DiscrepancyClass;
}

export interface ExecutiveReliabilityResolution {
  reliability: ExecutiveDataReliability;
  variant?: ExecutiveReliabilityVariant;
  allowsSimulator: boolean;
  allowsVerifiedExport: boolean;
}

const CONFIDENCE_UNAVAILABLE_REASONS = new Set([
  'insufficient_data',
  'unavailable_insufficient_data',
  'cold_start_insufficient_data',
  'bayesian_not_available',
]);

function normalizeMatchVerdict(raw: string | undefined | null): CanonicalMatchVerdict | 'unknown' {
  if (!raw?.trim()) return 'unknown';
  const key = raw.trim().toLowerCase().replace(/-/g, '_');

  if (key === 'matched_confirmed' || key === 'verified') return 'matched_confirmed';
  if (key === 'matched_provisional') return 'matched_provisional';
  if (key === 'adjusted' || key === 'flagged') return 'adjusted';
  if (key === 'within_tolerance') return 'matched_confirmed';
  if (key === 'unmatched' || key === 'rejected') return 'unmatched';
  if (key === 'pending') return 'pending';
  if (key === 'failed' || key === 'unavailable') return 'failed';
  return 'unknown';
}

function resolveCanonicalMatch(input: ExecutiveReliabilityInput): CanonicalMatchVerdict | 'unknown' {
  if (input.verificationStatus === 'unverified' || input.verificationStatus === 'disputed') {
    return 'unmatched';
  }
  if (input.verificationStatus === 'partial') {
    return 'matched_provisional';
  }

  const normalized = normalizeMatchVerdict(input.matchVerdict);
  if (normalized !== 'unknown') return normalized;
  return 'unknown';
}

function confidenceUnavailableVariant(
  reason: string | undefined,
): ExecutiveReliabilityVariant | undefined {
  const normalized = reason?.trim().toLowerCase().replace(/-/g, '_') ?? '';
  if (normalized.includes('timeout')) return 'confidence_paused';
  if (normalized.includes('nonconverged') || normalized.includes('non_converged')) {
    return 'confidence_updating';
  }
  if (
    CONFIDENCE_UNAVAILABLE_REASONS.has(normalized) ||
    normalized.includes('insufficient')
  ) {
    return 'confidence_building';
  }
  return 'confidence_building';
}

/** Fail-closed: unknown backend combinations never map to Verified. */
export function resolveExecutiveDataReliability(
  input: ExecutiveReliabilityInput,
): ExecutiveReliabilityResolution {
  const canonical = resolveCanonicalMatch(input);
  const freshness = input.extractionFreshness ?? 'fresh';
  const confidenceStatus = input.confidence?.status;
  const confidenceReason = input.confidence?.reason ?? input.fallbackReason ?? undefined;
  const discrepancyClass = input.discrepancyClass;

  // Highest-precedence override (Audit 1 + 2): a flagged/material discrepancy means the
  // platform claims revenue the commerce evidence does not support. This must surface as a
  // red Discrepancy verdict regardless of match/confidence — it is the "system lying by
  // omission" both audits condemn. An unknown discrepancy class fails closed to Discrepancy
  // rather than silently returning a reassuring Verified.
  if (discrepancyClass === 'flagged' || discrepancyClass === 'material') {
    return {
      reliability: 'discrepancy',
      variant: discrepancyClass === 'material' ? 'material' : 'flagged',
      allowsSimulator: false,
      allowsVerifiedExport: false,
    };
  }
  if (discrepancyClass === 'unknown') {
    return {
      reliability: 'discrepancy',
      variant: 'flagged',
      allowsSimulator: false,
      allowsVerifiedExport: false,
    };
  }

  if (freshness === 'failed' || canonical === 'failed') {
    return {
      reliability: 'unavailable',
      allowsSimulator: false,
      allowsVerifiedExport: false,
    };
  }

  if (canonical === 'unmatched') {
    if (freshness === 'stale' || confidenceStatus === 'delayed') {
      return {
        reliability: 'pending',
        allowsSimulator: false,
        allowsVerifiedExport: false,
      };
    }
    return {
      reliability: 'unavailable',
      allowsSimulator: false,
      allowsVerifiedExport: false,
    };
  }

  if (canonical === 'pending' || confidenceStatus === 'delayed') {
    return {
      reliability: 'pending',
      allowsSimulator: false,
      allowsVerifiedExport: false,
    };
  }

  if (canonical === 'matched_provisional') {
    return {
      reliability: 'estimated',
      variant: 'matched_provisional',
      allowsSimulator: false,
      allowsVerifiedExport: false,
    };
  }

  if (canonical === 'adjusted') {
    return {
      reliability: 'estimated',
      allowsSimulator: false,
      allowsVerifiedExport: false,
    };
  }

  if (confidenceStatus === 'unavailable') {
    return {
      reliability: 'estimated',
      variant: confidenceUnavailableVariant(confidenceReason),
      allowsSimulator: false,
      allowsVerifiedExport: false,
    };
  }

  if (canonical === 'matched_confirmed' && confidenceStatus === 'available') {
    return {
      reliability: 'verified',
      allowsSimulator: true,
      allowsVerifiedExport: true,
    };
  }

  if (canonical === 'matched_confirmed') {
    return {
      reliability: 'estimated',
      variant: confidenceUnavailableVariant(confidenceReason),
      allowsSimulator: false,
      allowsVerifiedExport: false,
    };
  }

  return {
    reliability: 'estimated',
    allowsSimulator: false,
    allowsVerifiedExport: false,
  };
}

export function allowsVerifiedExport(resolution: ExecutiveReliabilityResolution): boolean {
  return resolution.allowsVerifiedExport;
}

export function allowsBudgetSimulator(resolution: ExecutiveReliabilityResolution): boolean {
  return resolution.allowsSimulator;
}

export function resolveTrustEnvelopeExecutiveReliability(input: {
  matchVerdictStatus: string;
  confidence: Pick<ConfidenceShape, 'status' | 'reason'>;
  extractionFreshness?: ExtractionFreshness;
}): ExecutiveReliabilityResolution {
  return resolveExecutiveDataReliability({
    matchVerdict: input.matchVerdictStatus,
    confidence: input.confidence,
    extractionFreshness: input.extractionFreshness,
  });
}

export function resolveClaimExecutiveReliability(
  detail: Pick<ClaimDetailDTO, 'verificationStatus' | 'confidence' | 'discrepancyClass'>,
): ExecutiveReliabilityResolution {
  return resolveExecutiveDataReliability({
    matchVerdict: claimLedgerMatchVerdictFromDetail(detail),
    confidence: detail.confidence,
    verificationStatus: detail.verificationStatus,
    discrepancyClass: detail.discrepancyClass,
  });
}

function claimLedgerMatchVerdictFromDetail(
  detail: Pick<ClaimDetailDTO, 'verificationStatus' | 'discrepancyClass'>,
): string {
  if (detail.verificationStatus === 'unverified') return 'unavailable';
  if (detail.verificationStatus === 'partial') return 'matched_provisional';
  if (detail.discrepancyClass === 'material') return 'rejected';
  if (detail.discrepancyClass === 'flagged') return 'flagged';
  return 'within_tolerance';
}

export function resolveClaimLedgerExecutiveReliability(row: {
  matchVerdict: string;
  confidence: ConfidenceShape;
  verificationStatus: ClaimDetailDTO['verificationStatus'];
  discrepancyClass: DiscrepancyClass;
}): ExecutiveReliabilityResolution {
  return resolveExecutiveDataReliability({
    matchVerdict: row.matchVerdict,
    confidence: row.confidence,
    verificationStatus: row.verificationStatus,
    discrepancyClass: row.discrepancyClass,
  });
}

export function resolveTrustIndexExecutiveReliability(row: {
  matchVerdict: string;
  confidence: ConfidenceShape;
  verificationStatus: ClaimDetailDTO['verificationStatus'];
  discrepancyClass: DiscrepancyClass;
}): ExecutiveReliabilityResolution {
  return resolveExecutiveDataReliability({
    matchVerdict: row.matchVerdict,
    confidence: row.confidence,
    verificationStatus: row.verificationStatus,
    discrepancyClass: row.discrepancyClass,
  });
}
