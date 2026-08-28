import { useCallback, useState } from 'react';
import { Toast } from '../components/layout/Toast/Toast';
import { DETAIL_COPY } from './copy';
import shared from '../styles/shared.module.css';
import styles from './Level9BlockedAffordance.module.css';

export interface Level9BlockedAffordanceProps {
  actionLabel: string;
  disabled?: boolean;
}

export function Level9BlockedAffordance({ actionLabel, disabled = false }: Level9BlockedAffordanceProps) {
  const [toastVisible, setToastVisible] = useState(false);

  const handleClick = useCallback(() => {
    setToastVisible(true);
  }, []);

  return (
    <>
      <button
        type="button"
        className={[styles.button, shared.focusVisible].join(' ')}
        data-level9-blocked-action
        aria-label={`${actionLabel}. ${DETAIL_COPY.level9BlockedPrefix}.`}
        aria-describedby={`level9-blocked-${actionLabel.replace(/\s+/g, '-')}`}
        disabled={disabled}
        onClick={handleClick}
      >
        {actionLabel}
      </button>
      <span id={`level9-blocked-${actionLabel.replace(/\s+/g, '-')}`} className={styles.srOnly}>
        {DETAIL_COPY.level9BlockedReason(actionLabel)}
      </span>
      {toastVisible ? (
        <Toast
          severity="info"
          message={DETAIL_COPY.level9BlockedReason(actionLabel)}
          open={toastVisible}
          onDismiss={() => setToastVisible(false)}
        />
      ) : null}
    </>
  );
}
