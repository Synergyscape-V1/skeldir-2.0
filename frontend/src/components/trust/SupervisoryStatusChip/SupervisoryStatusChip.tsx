import type { HTMLAttributes, ReactNode } from 'react';
import styles from './SupervisoryStatusChip.module.css';

export type SupervisoryStatusTone = 'success' | 'error' | 'warning' | 'neutral';

export interface SupervisoryStatusChipProps extends HTMLAttributes<HTMLSpanElement> {
  tone: SupervisoryStatusTone;
  children: ReactNode;
}

export function SupervisoryStatusChip({
  tone,
  children,
  className,
  ...rest
}: SupervisoryStatusChipProps) {
  return (
    <span
      className={[styles.chip, styles[tone], className].filter(Boolean).join(' ')}
      role="status"
      data-trust-chip
      {...rest}
    >
      {children}
    </span>
  );
}
