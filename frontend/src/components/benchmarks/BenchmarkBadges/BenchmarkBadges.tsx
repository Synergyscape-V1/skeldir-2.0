import type { HTMLAttributes, ReactNode } from 'react';
import type {
  BenchmarkActionability,
  BenchmarkComparability,
  BenchmarkCoverageClass,
  BenchmarkEvidenceClass,
} from '../../../ledger/types';
import {
  actionabilityLabel,
  comparabilityLabel,
  coverageClassLabel,
  evidenceClassLabel,
  isValidActionability,
  isValidCoverageClass,
  isValidEvidenceClass,
} from '../../../benchmarks/benchmarkDisplay';
import { BENCHMARKS_COPY } from '../../../benchmarks/copy';
import statusText from '../../../styles/trustStatusText.module.css';
import { TrustChip, trustChipClassNames, type TrustChipTone } from '../../trust/TrustChip/TrustChip';

const EVIDENCE_TONE: Record<BenchmarkEvidenceClass, TrustChipTone> = {
  live_empirical: 'benchmark',
  tenant_longitudinal: 'info',
  historical_prior: 'warning',
  public_prior: 'warning',
  unavailable: 'neutral',
};

const COVERAGE_TONE: Record<BenchmarkCoverageClass, TrustChipTone> = {
  exact: 'success',
  broad: 'info',
  tenant_only: 'info',
  prior: 'warning',
  insufficient: 'neutral',
};

const ACTIONABILITY_TONE: Record<BenchmarkActionability, TrustChipTone> = {
  simulate: 'success',
  observe_only_until_stable: 'warning',
  blocked: 'error',
};

const COMPARABILITY_TONE: Record<BenchmarkComparability, TrustChipTone> = {
  comparable: 'success',
  not_comparable: 'warning',
  source_changed: 'error',
  unavailable: 'neutral',
};

const TONE_TEXT_CLASS: Record<TrustChipTone, string> = {
  success: statusText.labelSuccess,
  warning: statusText.labelWarning,
  error: statusText.labelError,
  info: statusText.labelInfo,
  neutral: statusText.labelNeutral,
  probabilistic: statusText.labelProbabilistic,
  benchmark: statusText.labelBenchmark,
  deterministic: statusText.labelSuccess,
};

type BenchmarkBadgeOptions = {
  variant?: 'chip' | 'text';
  table?: boolean;
  compact?: boolean;
};

function toneTextClass(tone: TrustChipTone, invalid = false): string {
  if (invalid) return statusText.labelError;
  return TONE_TEXT_CLASS[tone];
}

function BenchmarkStatusLabel({
  tone,
  invalid,
  variant = 'chip',
  children,
  ...rest
}: {
  tone: TrustChipTone;
  invalid?: boolean;
  variant?: 'chip' | 'text';
  children: ReactNode;
} & HTMLAttributes<HTMLSpanElement>) {
  if (variant === 'text') {
    return (
      <span
        className={toneTextClass(tone, invalid)}
        role={invalid ? 'alert' : 'status'}
        data-status-text
        {...rest}
      >
        {children}
      </span>
    );
  }

  return (
    <TrustChip tone={tone} invalid={invalid} {...rest}>
      {children}
    </TrustChip>
  );
}

export function EvidenceClassBadge({
  value,
  variant = 'chip',
  showHistoricalDisclaimer = false,
}: { value: BenchmarkEvidenceClass | string; showHistoricalDisclaimer?: boolean } & BenchmarkBadgeOptions) {
  if (!isValidEvidenceClass(value)) {
    return (
      <BenchmarkStatusLabel
        tone="error"
        variant={variant}
        role="alert"
        data-evidence-class-badge={value}
        invalid
      >
        Invalid evidence class
      </BenchmarkStatusLabel>
    );
  }

  const label = evidenceClassLabel(value);
  return (
    <>
      <BenchmarkStatusLabel
        tone={EVIDENCE_TONE[value]}
        variant={variant}
        data-evidence-class-badge={value}
        aria-label={`${label}. Source authority: ${value.replace(/_/g, ' ')}`}
      >
        {label}
      </BenchmarkStatusLabel>
      {showHistoricalDisclaimer && value === 'historical_prior' ? (
        <span className={statusText.labelWarning} data-historical-prior-disclaimer role="note">
          {BENCHMARKS_COPY.table.historicalPriorDisclaimer}
        </span>
      ) : null}
    </>
  );
}

export function CoverageClassBadge({
  value,
  variant = 'chip',
  title,
}: { value: BenchmarkCoverageClass | string; title?: string } & BenchmarkBadgeOptions) {
  if (!isValidCoverageClass(value)) {
    return (
      <BenchmarkStatusLabel
        tone="error"
        variant={variant}
        role="alert"
        data-coverage-class-badge={value}
        invalid
      >
        Invalid coverage class
      </BenchmarkStatusLabel>
    );
  }

  return (
    <BenchmarkStatusLabel
      tone={COVERAGE_TONE[value]}
      variant={variant}
      data-coverage-class-badge={value}
      aria-label={coverageClassLabel(value)}
      title={title}
    >
      {coverageClassLabel(value)}
    </BenchmarkStatusLabel>
  );
}

export function ActionabilityPill({
  value,
  variant = 'chip',
}: {
  value: BenchmarkActionability | string;
} & BenchmarkBadgeOptions) {
  if (!isValidActionability(value)) {
    return (
      <BenchmarkStatusLabel
        tone="error"
        variant={variant}
        role="alert"
        data-actionability-pill={value}
        invalid
      >
        Invalid actionability state
      </BenchmarkStatusLabel>
    );
  }

  const fullLabel = actionabilityLabel(value);

  return (
    <BenchmarkStatusLabel
      tone={ACTIONABILITY_TONE[value]}
      variant={variant}
      data-actionability-pill={value}
      aria-label={fullLabel}
    >
      {fullLabel}
    </BenchmarkStatusLabel>
  );
}

export function ComparabilityIndicator({
  value,
  variant = 'chip',
  sourceTransition = false,
}: { value: BenchmarkComparability | string; sourceTransition?: boolean } & BenchmarkBadgeOptions) {
  if (sourceTransition || value === 'source_changed') {
    return (
      <BenchmarkStatusLabel
        tone="error"
        variant={variant}
        data-comparability-indicator="estimator_transition"
        data-estimator-transition-badge
        aria-label={BENCHMARKS_COPY.table.estimatorTransitionTooltip}
        title={BENCHMARKS_COPY.table.estimatorTransitionTooltip}
      >
        {BENCHMARKS_COPY.table.estimatorTransitionBadge}
      </BenchmarkStatusLabel>
    );
  }

  const label = comparabilityLabel(value as BenchmarkComparability);

  if (label.startsWith('Invalid')) {
    return (
      <BenchmarkStatusLabel
        tone="error"
        variant={variant}
        role="alert"
        data-comparability-indicator={value}
        invalid
      >
        {label}
      </BenchmarkStatusLabel>
    );
  }

  return (
    <BenchmarkStatusLabel
      tone={COMPARABILITY_TONE[value as BenchmarkComparability]}
      variant={variant}
      data-comparability-indicator={value}
      aria-label={label}
    >
      {label}
    </BenchmarkStatusLabel>
  );
}

export { trustChipClassNames as benchmarkTrustChipClassNames };
