import type { HTMLAttributes } from 'react';
import styles from './Skeleton.module.css';

export interface SkeletonProps extends HTMLAttributes<HTMLDivElement> {
  rows?: number;
  variant?: 'text' | 'block' | 'row';
}

export function Skeleton({ rows = 1, variant = 'text', className, ...rest }: SkeletonProps) {
  return (
    <div className={[styles.wrapper, className].filter(Boolean).join(' ')} aria-hidden="true" {...rest}>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className={styles[variant]} />
      ))}
    </div>
  );
}
