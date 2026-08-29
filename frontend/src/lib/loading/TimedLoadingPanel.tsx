import type { ReactNode } from 'react';
import { Skeleton } from '../../components/layout/Skeleton/Skeleton';
import { LOADING_COPY } from '../copy';
import shared from '../../styles/shared.module.css';
import styles from './TimedLoadingPanel.module.css';
import { useTimedLoading } from './useTimedLoading';

export interface TimedLoadingPanelProps {
  active: boolean;
  progressCopy?: string;
  onRetry?: () => void;
  skeletonRows?: number;
  skeletonVariant?: 'text' | 'block' | 'row';
  children?: ReactNode;
  className?: string;
  'data-testid'?: string;
}

/** Skeleton-first loading surface with spec-compliant 2s / 8s escalation. */
export function TimedLoadingPanel({
  active,
  progressCopy = LOADING_COPY.progress,
  onRetry,
  skeletonRows = 6,
  skeletonVariant = 'block',
  children,
  className,
  'data-testid': dataTestId,
}: TimedLoadingPanelProps) {
  const phase = useTimedLoading(active);

  if (!active) return null;

  return (
    <div
      className={[styles.panel, className].filter(Boolean).join(' ')}
      aria-busy="true"
      data-timed-loading={phase ?? 'under_2s'}
      data-testid={dataTestId}
    >
      {children ?? <Skeleton rows={skeletonRows} variant={skeletonVariant} />}
      {phase === 'over_2s' || phase === 'over_8s' ? (
        <p role="status" aria-live="polite" className={styles.progress}>
          {progressCopy}
        </p>
      ) : null}
      {phase === 'over_8s' && onRetry ? (
        <button type="button" className={[styles.retry, shared.focusVisible].join(' ')} onClick={onRetry}>
          {LOADING_COPY.retry}
        </button>
      ) : null}
    </div>
  );
}
