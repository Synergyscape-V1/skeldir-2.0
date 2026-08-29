import type { ConfidenceShape } from '../../../ledger/types';
import { DataUnavailablePanel } from '../../trust/DataUnavailablePanel/DataUnavailablePanel';
import styles from './ConfidenceCell.module.css';

export function ConfidenceCell({ confidence }: { confidence: ConfidenceShape }) {
  if (confidence.status === 'unavailable') {
    return (
      <div data-confidence-cell="unavailable">
        <DataUnavailablePanel
          variant="no_confidence"
          reason={confidence.reason ?? 'Confidence is unavailable. Deterministic verification remains active.'}
        />
      </div>
    );
  }

  if (confidence.status === 'available') {
    const hasShape =
      confidence.intervalLower !== undefined ||
      confidence.intervalUpper !== undefined ||
      confidence.methodOrContext ||
      confidence.qualitativeState;

    if (!hasShape) {
      return (
        <div className={styles.error} role="alert" data-confidence-cell="naked-scalar">
          Invalid confidence shape
        </div>
      );
    }

    return (
      <div data-confidence-cell="shaped" className={styles.shaped}>
        {confidence.intervalLower !== undefined && confidence.intervalUpper !== undefined ? (
          <span className={styles.interval}>
            {confidence.intervalLower}–{confidence.intervalUpper}
          </span>
        ) : null}
        {confidence.methodOrContext ? (
          <span className={styles.method}>{confidence.methodOrContext}</span>
        ) : null}
        {confidence.qualitativeState ? (
          <span className={styles.qualitative}>{confidence.qualitativeState}</span>
        ) : null}
      </div>
    );
  }

  return (
    <div data-confidence-cell="delayed" role="status">
      Confidence delayed
      {confidence.reason ? <span className={styles.method}> — {confidence.reason}</span> : null}
    </div>
  );
}
