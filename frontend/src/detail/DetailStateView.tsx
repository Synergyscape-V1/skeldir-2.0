import { Link } from 'react-router-dom';
import { ErrorBanner } from '../components/layout/ErrorBanner/ErrorBanner';
import { Skeleton } from '../components/layout/Skeleton/Skeleton';
import type { ActiveLoadingPhase } from '../lib/loading';
import { LOADING_COPY } from '../lib/copy';
import type { DetailOutcomeKind } from './types';
import { DETAIL_COPY } from './copy';
import { buildParentReturnLink, type ParentReturnContext } from './parentContext';
import shared from '../styles/shared.module.css';
import styles from './DetailStateView.module.css';

const ERROR_MESSAGES: Partial<Record<DetailOutcomeKind, string>> = {
  not_found: DETAIL_COPY.notFound,
  permission_denied: DETAIL_COPY.permissionDenied,
  scope_denied: DETAIL_COPY.scopeDenied,
  object_id_mismatch: DETAIL_COPY.objectIdMismatch,
  stale_version: DETAIL_COPY.staleVersion,
  corrupted_evidence: DETAIL_COPY.corruptedEvidence,
  schema_invalid: DETAIL_COPY.schemaInvalid,
  network_error: DETAIL_COPY.networkError,
  trust_api_error: DETAIL_COPY.trustApiError,
  unavailable: DETAIL_COPY.trustApiError,
  audit_unavailable: 'Audit reference is unavailable for this object.',
  confidence_unavailable: 'Confidence metadata is unavailable for this object.',
  benchmark_unavailable: 'Benchmark context is unavailable for this object.',
};

export interface DetailStateViewProps {
  kind: DetailOutcomeKind | 'idle';
  message?: string;
  loadingPhase?: ActiveLoadingPhase | null;
  parentContext?: ParentReturnContext;
  onRetry?: () => void;
}

export function DetailStateView({
  kind,
  message,
  loadingPhase,
  parentContext,
  onRetry,
}: DetailStateViewProps) {
  if (kind === 'loading' || kind === 'idle') {
    const showProgress = loadingPhase === 'over_2s' || loadingPhase === 'over_8s';
    const showRetry = loadingPhase === 'over_8s' && onRetry;

    return (
      <div data-detail-state="loading" aria-busy="true" className={styles.statePanel}>
        <Skeleton rows={6} variant="text" />
        {showProgress ? (
          <p role="status" aria-live="polite" className={styles.progress}>
            {LOADING_COPY.progress}
          </p>
        ) : null}
        {showRetry ? (
          <button
            type="button"
            className={[styles.retry, shared.focusVisible].join(' ')}
            onClick={onRetry}
          >
            {LOADING_COPY.retry}
          </button>
        ) : null}
      </div>
    );
  }

  if (kind === 'loaded') return null;

  const resolvedMessage = message ?? ERROR_MESSAGES[kind] ?? 'Detail unavailable.';
  return (
    <div data-detail-state={kind} className={styles.statePanel} role="alert">
      <ErrorBanner variant="error" message={resolvedMessage} />
      {parentContext ? (
        <Link
          to={buildParentReturnLink(parentContext)}
          className={[styles.returnLink, shared.focusVisible].join(' ')}
          data-detail-parent-fallback
        >
          {parentContext.returnLabel}
        </Link>
      ) : null}
      {onRetry ? (
        <button type="button" className={[styles.retry, shared.focusVisible].join(' ')} onClick={onRetry}>
          {LOADING_COPY.retry}
        </button>
      ) : null}
    </div>
  );
}

