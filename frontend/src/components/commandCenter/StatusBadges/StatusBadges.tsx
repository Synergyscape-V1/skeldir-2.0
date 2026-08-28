import type {
  BayesianStatusKey,
  BenchmarkStatusKey,
  DiscrepancyStatus,
  RecentEnvelopeStatusKey,
} from '../../../commandCenter/types';
import type { DiscrepancyClass, MatchVerdictStatus } from '../../../ledger/types';
import { formatBpsAsPercentOneDecimal } from '../../../lib/money';
import styles from './StatusBadges.module.css';

const DISCREPANCY_LABELS: Record<DiscrepancyStatus, string> = {
  rejected: 'Rejected',
  flagged: 'Flagged',
  within_tolerance: 'Within tolerance',
  unavailable: 'Unavailable',
};

const DISCREPANCY_TABLE_TEXT_LABELS: Record<DiscrepancyStatus, string> = {
  rejected: 'Rejected',
  flagged: 'Flagged',
  within_tolerance: 'Within tolerance',
  unavailable: 'Unavailable',
};

const BAYESIAN_LABELS: Record<BayesianStatusKey, string> = {
  healthy: 'Healthy',
  low_confidence: 'Low confidence',
  unavailable: 'Unavailable',
  delayed: 'Delayed',
};

const BAYESIAN_TABLE_TEXT_LABELS: Record<BayesianStatusKey, string> = {
  healthy: 'Healthy',
  low_confidence: 'Low confidence',
  unavailable: 'Unavailable',
  delayed: 'Delayed',
};

const BENCHMARK_LABELS: Record<BenchmarkStatusKey, string> = {
  stable: 'Stable',
  transitioning: 'Transitioning',
  unavailable: 'Unavailable',
  suppressed: 'Suppressed',
};

const BENCHMARK_TABLE_TEXT_LABELS: Record<BenchmarkStatusKey, string> = {
  stable: 'Stable',
  transitioning: 'Transitioning',
  unavailable: 'Unavailable',
  suppressed: 'Suppressed',
};

export function formatDiscrepancyPercent(bps: number): string {
  return formatBpsAsPercentOneDecimal(bps);
}

const ENVELOPE_STATUS_LABELS: Record<RecentEnvelopeStatusKey, string> = {
  verified: 'Verified',
  pending_approval: 'Pending approval',
  transitioning: 'Transitioning',
};

/**
 * Verdict register — the reconciliation conclusion, deliberately distinct from the
 * Difference column's variance-band vocabulary (Within tolerance / Flagged / Alert).
 * Difference owns magnitude + band; Match verdict owns the conclusion. Keeping these
 * in separate registers stops the two adjacent columns from restating the same word.
 */
const MATCH_VERDICT_LABELS: Record<MatchVerdictStatus, string> = {
  verified: 'Verified',
  within_tolerance: 'Matched',
  flagged: 'Needs review',
  rejected: 'Rejected',
  unavailable: 'Unavailable',
};

function matchVerdictStyleClass(status: MatchVerdictStatus): string {
  if (status === 'verified') return styles.envelope_verified;
  return styles[status];
}

export function discrepancyClassBadgeClass(discrepancyClass: DiscrepancyClass): string {
  if (discrepancyClass === 'within_tolerance') return styles.within_tolerance;
  if (discrepancyClass === 'flagged') return styles.flagged;
  if (discrepancyClass === 'material') return styles.rejected;
  return styles.unavailable;
}

export function matchVerdictBadgeTone(
  status: MatchVerdictStatus,
  discrepancyClass?: DiscrepancyClass,
): { styleClass: string; toneKey: string } {
  if (status === 'rejected') {
    return { styleClass: styles.rejected, toneKey: 'rejected' };
  }
  if (status === 'unavailable') {
    return { styleClass: styles.unavailable, toneKey: 'unavailable' };
  }
  if (discrepancyClass) {
    return { styleClass: discrepancyClassBadgeClass(discrepancyClass), toneKey: discrepancyClass };
  }
  return { styleClass: matchVerdictStyleClass(status), toneKey: status };
}

function chipClasses(
  styleClass: string,
  options?: { compact?: boolean; table?: boolean },
): string {
  const table = options?.table ?? false;
  const compact = options?.compact ?? table;
  return [styles.badge, styleClass, compact ? styles.compact : '', table ? styles.table : '']
    .filter(Boolean)
    .join(' ');
}

type StatusBadgeOptions = { compact?: boolean; table?: boolean; variant?: 'chip' | 'text' };

const DISCREPANCY_TEXT_CLASS: Record<DiscrepancyStatus, string> = {
  rejected: styles.rejectedText,
  flagged: styles.flaggedText,
  within_tolerance: styles.within_toleranceText,
  unavailable: styles.unavailableText,
};

const BAYESIAN_TEXT_CLASS: Record<BayesianStatusKey, string> = {
  healthy: styles.bayesian_healthyText,
  low_confidence: styles.bayesian_low_confidenceText,
  unavailable: styles.bayesian_unavailableText,
  delayed: styles.bayesian_delayedText,
};

const BENCHMARK_TEXT_CLASS: Record<BenchmarkStatusKey, string> = {
  stable: styles.benchmark_stableText,
  transitioning: styles.benchmark_transitioningText,
  unavailable: styles.benchmark_unavailableText,
  suppressed: styles.benchmark_suppressedText,
};

function statusChipProps(options?: StatusBadgeOptions) {
  if (options?.variant === 'text') {
    return { 'data-status-text': true as const };
  }
  return options?.table ? { 'data-trust-chip': true as const } : {};
}

const ENVELOPE_TEXT_CLASS: Record<RecentEnvelopeStatusKey, string> = {
  verified: styles.envelope_verifiedText,
  pending_approval: styles.envelope_pending_approvalText,
  transitioning: styles.envelope_transitioningText,
};

export function EnvelopeStatusLabel({
  status,
  variant = 'chip',
  table = true,
  compact,
}: {
  status: RecentEnvelopeStatusKey | string;
  variant?: 'chip' | 'text';
  table?: boolean;
  compact?: boolean;
}) {
  const key = status as RecentEnvelopeStatusKey;
  if (!ENVELOPE_STATUS_LABELS[key]) {
    const className =
      variant === 'text' ? styles.unavailableText : chipClasses(styles.unavailable, { table: true });
    return (
      <span
        className={className}
        data-envelope-status={status}
        {...(variant === 'text' ? { 'data-status-text': true } : { 'data-trust-chip': true })}
        role="alert"
      >
        Invalid envelope status
      </span>
    );
  }

  const className =
    variant === 'text'
      ? ENVELOPE_TEXT_CLASS[key]
      : chipClasses(styles[`envelope_${key}`], { compact, table });

  return (
    <span
      className={className}
      data-envelope-status={key}
      {...statusChipProps({ compact, table, variant })}
    >
      {ENVELOPE_STATUS_LABELS[key]}
    </span>
  );
}

export function DiscrepancyBadge({
  status,
  compact,
  table,
  variant = 'chip',
}: {
  status: DiscrepancyStatus;
  compact?: boolean;
  table?: boolean;
  variant?: 'chip' | 'text';
}) {
  const className =
    variant === 'text'
      ? DISCREPANCY_TEXT_CLASS[status]
      : chipClasses(styles[status], { compact, table });
  const label = variant === 'text' ? DISCREPANCY_TABLE_TEXT_LABELS[status] : DISCREPANCY_LABELS[status];

  return (
    <span
      className={className}
      data-discrepancy-badge={status}
      {...statusChipProps({ compact, table, variant })}
    >
      {label}
    </span>
  );
}

function matchVerdictTextClass(toneKey: string): string {
  const toneClassByKey: Record<string, string> = {
    rejected: styles.rejectedText,
    unavailable: styles.unavailableText,
    within_tolerance: styles.within_toleranceText,
    flagged: styles.flaggedText,
    verified: styles.envelope_verifiedText,
    material: styles.rejectedText,
  };
  return toneClassByKey[toneKey] ?? styles.unavailableText;
}

export function MatchVerdictBadge({
  status,
  table,
  discrepancyClass,
  variant = 'chip',
}: {
  status: MatchVerdictStatus;
  table?: boolean;
  discrepancyClass?: DiscrepancyClass;
  variant?: 'chip' | 'text';
}) {
  if (!MATCH_VERDICT_LABELS[status]) {
    const className =
      variant === 'text' ? styles.unavailableText : chipClasses(styles.unavailable, { table });
    return (
      <span
        className={className}
        data-match-verdict={status}
        {...(variant === 'text' ? { 'data-status-text': true } : table ? { 'data-trust-chip': true } : {})}
        role="alert"
      >
        Invalid match verdict
      </span>
    );
  }

  const { styleClass, toneKey } = matchVerdictBadgeTone(status, discrepancyClass);
  const className =
    variant === 'text' ? matchVerdictTextClass(toneKey) : chipClasses(styleClass, { table });

  return (
    <span
      className={className}
      data-match-verdict={status}
      data-match-verdict-tone={toneKey}
      {...statusChipProps({ table, variant })}
    >
      {MATCH_VERDICT_LABELS[status]}
    </span>
  );
}

export function BayesianStatusBadge({
  status,
  compact,
  table,
  variant = 'chip',
}: {
  status: BayesianStatusKey;
  compact?: boolean;
  table?: boolean;
  variant?: 'chip' | 'text';
}) {
  const className =
    variant === 'text'
      ? BAYESIAN_TEXT_CLASS[status]
      : chipClasses(styles[`bayesian_${status}`], { compact, table });
  const label = variant === 'text' ? BAYESIAN_TABLE_TEXT_LABELS[status] : BAYESIAN_LABELS[status];

  return (
    <span
      className={className}
      data-bayesian-status={status}
      {...statusChipProps({ compact, table, variant })}
    >
      {label}
    </span>
  );
}

export function BenchmarkStatusBadge({
  status,
  compact,
  table,
  variant = 'chip',
}: {
  status: BenchmarkStatusKey;
  compact?: boolean;
  table?: boolean;
  variant?: 'chip' | 'text';
}) {
  const className =
    variant === 'text'
      ? BENCHMARK_TEXT_CLASS[status]
      : chipClasses(styles[`benchmark_${status}`], { compact, table });
  const label = variant === 'text' ? BENCHMARK_TABLE_TEXT_LABELS[status] : BENCHMARK_LABELS[status];

  return (
    <span
      className={className}
      data-benchmark-status={status}
      {...statusChipProps({ compact, table, variant })}
    >
      {label}
    </span>
  );
}

export type SignatureStatusKey = 'verified' | 'requires_review' | 'unavailable';

const SIGNATURE_LABELS: Record<SignatureStatusKey, string> = {
  verified: 'Verified',
  requires_review: 'Requires review',
  unavailable: 'Unavailable',
};

const TABLE_SIGNATURE_LABELS: Record<SignatureStatusKey, string> = {
  verified: 'Verified',
  requires_review: 'Review',
  unavailable: 'Unavailable',
};

const TABLE_SIGNATURE_TEXT_LABELS: Record<SignatureStatusKey, string> = {
  verified: 'Verified',
  requires_review: 'Review',
  unavailable: 'Unavailable',
};

function signatureStatusStyleClass(status: SignatureStatusKey): string {
  if (status === 'verified') return styles.envelope_verified;
  if (status === 'requires_review') return styles.envelope_pending_approval;
  return styles.unavailable;
}

const SIGNATURE_TEXT_CLASS: Record<SignatureStatusKey, string> = {
  verified: styles.envelope_verifiedText,
  requires_review: styles.envelope_pending_approvalText,
  unavailable: styles.unavailableText,
};

export function SignatureStatusBadge({
  status,
  compact,
  table,
  variant = 'chip',
}: {
  status: SignatureStatusKey;
  compact?: boolean;
  table?: boolean;
  variant?: 'chip' | 'text';
}) {
  const label =
    variant === 'text'
      ? TABLE_SIGNATURE_TEXT_LABELS[status]
      : table
        ? TABLE_SIGNATURE_LABELS[status]
        : SIGNATURE_LABELS[status];
  const className =
    variant === 'text'
      ? SIGNATURE_TEXT_CLASS[status]
      : chipClasses(signatureStatusStyleClass(status), { compact, table });

  return (
    <span
      className={className}
      data-trust-index-signature={status}
      {...statusChipProps({ compact, table, variant })}
      title={table || variant === 'text' ? SIGNATURE_LABELS[status] : undefined}
    >
      {label}
    </span>
  );
}

export function PlatformClaimLabel({ compact, table }: { compact?: boolean; table?: boolean }) {
  return (
    <span
      className={chipClasses(styles.platformClaim, { compact: compact ?? table, table })}
      data-platform-claim-label
      {...(table ? { 'data-trust-chip': true } : {})}
    >
      {compact || table ? 'platform claim' : 'Platform claim'}
    </span>
  );
}
