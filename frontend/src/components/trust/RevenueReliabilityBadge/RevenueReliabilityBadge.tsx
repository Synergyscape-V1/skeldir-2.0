import type { HTMLAttributes } from 'react';
import type { RevenueReliabilityState } from '../../../trust/revenueReliability';
import {
  revenueReliabilityBadgeLabel,
  revenueReliabilityBadgeTooltip,
} from '../../../trust/revenueReliabilityCopy';
import { TrustChip, type TrustChipTone } from '../TrustChip/TrustChip';
import styles from './RevenueReliabilityBadge.module.css';

export interface RevenueReliabilityBadgeProps extends HTMLAttributes<HTMLSpanElement> {
  state: RevenueReliabilityState;
  invalid?: boolean;
}

const STATE_TONE: Record<RevenueReliabilityState, TrustChipTone> = {
  robust: 'deterministic',
  mixed: 'warning',
  fragile: 'error',
};

export function RevenueReliabilityBadge({
  state,
  invalid = false,
  className,
  ...rest
}: RevenueReliabilityBadgeProps) {
  const label = invalid ? 'Invalid reliability state' : revenueReliabilityBadgeLabel(state);
  const tooltip = invalid
    ? 'Unknown model agreement tier returned by backend.'
    : revenueReliabilityBadgeTooltip(state);

  return (
    <TrustChip
      tone={STATE_TONE[state]}
      invalid={invalid}
      className={[styles.badge, className].filter(Boolean).join(' ')}
      data-revenue-reliability={state}
      data-revenue-reliability-invalid={invalid ? 'true' : undefined}
      title={tooltip}
      aria-label={`${label}. ${tooltip}`}
      {...rest}
    >
      <span>{label}</span>
    </TrustChip>
  );
}
