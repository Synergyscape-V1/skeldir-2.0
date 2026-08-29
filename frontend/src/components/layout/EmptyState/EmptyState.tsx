import type { ReactNode } from 'react';
import { ERROR_COPY } from '../../../lib/copy';
import shared from '../../../styles/shared.module.css';
import styles from './EmptyState.module.css';

export interface EmptyStateProps {
  title: string;
  description?: string;
  action?: ReactNode;
  onClearFilters?: () => void;
  variant?: 'default' | 'filtered';
}

export function EmptyState({ title, description, action, onClearFilters, variant = 'default' }: EmptyStateProps) {
  if (!title) {
    return (
      <div className={shared.errorState} role="alert">
        {ERROR_COPY.missingRequiredProp('title')}
      </div>
    );
  }

  return (
    <div className={styles.empty} role="status">
      <h3 className={styles.title}>{title}</h3>
      {description ? <p className={styles.description}>{description}</p> : null}
      {variant === 'filtered' && onClearFilters ? (
        <button type="button" className={[styles.action, shared.focusVisible].join(' ')} onClick={onClearFilters}>
          Clear filters
        </button>
      ) : null}
      {action}
    </div>
  );
}
