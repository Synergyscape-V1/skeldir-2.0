import type { HTMLAttributes } from 'react';
import { IconInfo, IconWarning } from '../../icons/StatusIcons';
import type {
  ExecutiveDataReliability,
  ExecutiveReliabilityVariant,
} from '../../../trust/executiveDataReliability';
import {
  executiveReliabilityBadgeLabel,
  executiveReliabilityTooltip,
} from '../../../trust/executiveDataReliabilityCopy';
import { TrustChip, type TrustChipTone } from '../TrustChip/TrustChip';
import styles from './ExecutiveReliabilityBadge.module.css';

export interface ExecutiveReliabilityBadgeProps extends HTMLAttributes<HTMLSpanElement> {
  reliability: ExecutiveDataReliability;
  variant?: ExecutiveReliabilityVariant;
  showIcon?: boolean;
}

const RELIABILITY_TONE: Record<ExecutiveDataReliability, TrustChipTone> = {
  verified: 'success',
  estimated: 'warning',
  pending: 'neutral',
  unavailable: 'neutral',
  discrepancy: 'error',
};

export function ExecutiveReliabilityBadge({
  reliability,
  variant,
  showIcon = true,
  className,
  ...rest
}: ExecutiveReliabilityBadgeProps) {
  const label = executiveReliabilityBadgeLabel(reliability, variant);
  const tooltip = executiveReliabilityTooltip(reliability, variant);
  const Icon = reliability === 'verified' ? IconInfo : IconWarning;

  return (
    <TrustChip
      tone={RELIABILITY_TONE[reliability]}
      className={[styles.badge, className].filter(Boolean).join(' ')}
      data-executive-reliability={reliability}
      data-executive-reliability-variant={variant ?? undefined}
      title={tooltip}
      aria-label={`${label}. ${tooltip}`}
      {...rest}
    >
      {showIcon ? <Icon aria-hidden="true" className={styles.icon} /> : null}
      <span>{label}</span>
    </TrustChip>
  );
}
