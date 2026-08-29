import type { HTMLAttributes, ReactNode } from 'react';
import trustChip from '../../../styles/trustChip.module.css';

export type TrustChipTone =
  | 'success'
  | 'warning'
  | 'error'
  | 'info'
  | 'neutral'
  | 'deterministic'
  | 'probabilistic'
  | 'benchmark';

const TONE_CLASSES: Record<TrustChipTone, string> = {
  success: trustChip.toneSuccess,
  warning: trustChip.toneWarning,
  error: trustChip.toneError,
  info: trustChip.toneInfo,
  neutral: trustChip.toneNeutral,
  deterministic: trustChip.toneDeterministic,
  probabilistic: trustChip.toneProbabilistic,
  benchmark: trustChip.toneBenchmark,
};

/** Canonical compact table chip class list — matches AuthorityBadge `size="table"`. */
export const TABLE_CHIP_CLASS = [trustChip.chip, trustChip.table, trustChip.compact].join(' ');

export function trustChipClassNames(tone: TrustChipTone, invalid = false): string {
  if (invalid) {
    return [TABLE_CHIP_CLASS, trustChip.toneError].join(' ');
  }
  return [TABLE_CHIP_CLASS, TONE_CLASSES[tone]].join(' ');
}

export interface TrustChipProps extends HTMLAttributes<HTMLSpanElement> {
  tone: TrustChipTone;
  children: ReactNode;
  invalid?: boolean;
}

export function TrustChip({ tone, children, invalid, className, ...rest }: TrustChipProps) {
  return (
    <span
      className={[trustChipClassNames(tone, invalid), className].filter(Boolean).join(' ')}
      role="status"
      data-trust-chip
      {...rest}
    >
      {children}
    </span>
  );
}
