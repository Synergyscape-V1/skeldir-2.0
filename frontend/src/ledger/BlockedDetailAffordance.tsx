import { useCallback, useState } from 'react';
import { Toast } from '../components/layout/Toast/Toast';
import { LEDGER_COPY } from './copy';
import shared from '../styles/shared.module.css';
import styles from './BlockedDetailAffordance.module.css';

export interface BlockedDetailAffordanceProps {
  surfaceLabel: string;
  rowIdentity: string;
  returnFocusRef?: React.RefObject<HTMLElement | null>;
  disabled?: boolean;
}

export function BlockedDetailAffordance({
  surfaceLabel,
  rowIdentity,
  returnFocusRef,
  disabled = false,
}: BlockedDetailAffordanceProps) {
  const [toastVisible, setToastVisible] = useState(false);

  const handleClick = useCallback(() => {
    setToastVisible(true);
    returnFocusRef?.current?.focus();
  }, [returnFocusRef]);

  return (
    <>
      <button
        type="button"
        className={[styles.button, shared.focusVisible].join(' ')}
        data-detail-affordance="blocked"
        aria-label={LEDGER_COPY.detailBlockedAria(surfaceLabel)}
        aria-describedby={`blocked-detail-${rowIdentity}`}
        disabled={disabled}
        onClick={handleClick}
      >
        View detail
        <span className={styles.futureLabel}>Level 8</span>
      </button>
      <span id={`blocked-detail-${rowIdentity}`} className={styles.srOnly}>
        {LEDGER_COPY.detailBlockedBody(surfaceLabel)}
      </span>
      {toastVisible ? (
        <Toast
          severity="info"
          message={LEDGER_COPY.detailBlockedBody(surfaceLabel)}
          open={toastVisible}
          onDismiss={() => setToastVisible(false)}
        />
      ) : null}
    </>
  );
}

export function BlockedDetailPanel({ surfaceLabel }: { surfaceLabel: string }) {
  return (
    <section
      className={styles.panel}
      data-level8-blocked-panel
      role="status"
      aria-live="polite"
    >
      <h2 className={styles.panelTitle}>{LEDGER_COPY.detailBlockedTitle}</h2>
      <p>{LEDGER_COPY.detailBlockedBody(surfaceLabel)}</p>
      <a href="/app" className={[styles.returnLink, shared.focusVisible].join(' ')}>
        Return to app frame
      </a>
    </section>
  );
}
