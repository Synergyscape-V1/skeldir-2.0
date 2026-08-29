import type { HTMLAttributes, ReactNode } from 'react';
import { ERROR_COPY, LOADING_COPY } from '../../../lib/copy';
import styles from './Card.module.css';
import shared from '../../../styles/shared.module.css';

export type CardState =
  | 'uninitialized'
  | 'loading_under_2s'
  | 'loading_over_2s'
  | 'loading_over_8s'
  | 'empty'
  | 'populated'
  | 'partial'
  | 'error'
  | 'disabled';

export interface CardProps extends HTMLAttributes<HTMLElement> {
  title?: string;
  state?: CardState;
  progressCopy?: string;
  onRetry?: () => void;
  emptyMessage?: string;
  errorMessage?: string;
  disabledReason?: string;
  children?: ReactNode;
}

export function Card({
  title,
  state = 'populated',
  progressCopy,
  onRetry,
  emptyMessage,
  errorMessage,
  disabledReason,
  children,
  className,
  ...rest
}: CardProps) {
  if (state === 'error' && !errorMessage) {
    return (
      <div className={shared.errorState} role="alert">
        {ERROR_COPY.missingRequiredProp('errorMessage')}
      </div>
    );
  }

  if (state === 'empty' && !emptyMessage) {
    return (
      <div className={shared.errorState} role="alert">
        {ERROR_COPY.missingRequiredProp('emptyMessage')}
      </div>
    );
  }

  if (state === 'loading_over_8s' && !onRetry) {
    return (
      <div className={shared.errorState} role="alert">
        {ERROR_COPY.missingRequiredProp('onRetry for loading_over_8s')}
      </div>
    );
  }

  return (
    <section
      className={[styles.card, state === 'disabled' ? styles.disabled : '', className]
        .filter(Boolean)
        .join(' ')}
      aria-busy={state.startsWith('loading') ? true : undefined}
      aria-disabled={state === 'disabled' ? true : undefined}
      {...rest}
    >
      {title ? <h3 className={styles.title}>{title}</h3> : null}

      {state === 'loading_under_2s' || state === 'loading_over_2s' || state === 'loading_over_8s' ? (
        <div className={styles.skeletonBody} aria-hidden="true" />
      ) : null}

      {(state === 'loading_over_2s' || state === 'loading_over_8s') && (
        <p className={styles.progressCopy} aria-live="polite">
          {progressCopy ?? 'Still loading verified trust state…'}
        </p>
      )}

      {state === 'loading_over_8s' && onRetry ? (
        <button type="button" className={[styles.retryButton, shared.focusVisible].join(' ')} onClick={onRetry}>
          {LOADING_COPY.retry}
        </button>
      ) : null}

      {state === 'empty' && emptyMessage ? <p className={styles.message}>{emptyMessage}</p> : null}
      {state === 'error' && errorMessage ? (
        <p className={styles.errorMessage} role="alert">
          {errorMessage}
        </p>
      ) : null}
      {state === 'disabled' && disabledReason ? (
        <p className={styles.message}>{disabledReason}</p>
      ) : null}

      {(state === 'populated' || state === 'partial') && children}
    </section>
  );
}

