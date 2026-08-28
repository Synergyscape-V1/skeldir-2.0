import { useEffect, useRef, useState } from 'react';
import { IconError, IconInfo, IconSuccess, IconWarning } from '../../icons/StatusIcons';
import { ERROR_COPY, TOAST_COPY } from '../../../lib/copy';
import type { ToastSeverity } from '../../../lib/types';
import shared from '../../../styles/shared.module.css';
import styles from './Toast.module.css';

export interface ToastProps {
  severity: ToastSeverity | 'unknown';
  message?: string;
  open: boolean;
  onDismiss?: () => void;
  placement?: 'desktop' | 'mobile';
  showProgress?: boolean;
  progressDurationMs?: number;
}

const DEFAULT_MESSAGES: Record<ToastSeverity, string> = {
  success: TOAST_COPY.successExample,
  error: TOAST_COPY.errorExample,
  info: 'Information',
  warning: 'Warning',
};

export function Toast({
  severity,
  message,
  open,
  onDismiss,
  placement = 'desktop',
  showProgress = false,
  progressDurationMs = 5000,
}: ToastProps) {
  const dismissRef = useRef<HTMLButtonElement>(null);
  const [progress, setProgress] = useState(100);

  useEffect(() => {
    if (!open || severity === 'error' || severity === 'unknown') return;
    const timer = window.setTimeout(() => onDismiss?.(), progressDurationMs);
    return () => window.clearTimeout(timer);
  }, [open, severity, onDismiss, progressDurationMs]);

  useEffect(() => {
    if (!open || !showProgress || severity === 'error' || severity === 'unknown') {
      setProgress(100);
      return;
    }
    setProgress(100);
    const startedAt = performance.now();
    let frame = 0;
    const tick = (now: number) => {
      const elapsed = now - startedAt;
      const next = Math.max(0, 100 - (elapsed / progressDurationMs) * 100);
      setProgress(next);
      if (elapsed < progressDurationMs) {
        frame = window.requestAnimationFrame(tick);
      }
    };
    frame = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(frame);
  }, [open, showProgress, severity, progressDurationMs]);

  if (!open) return null;

  if (severity === 'unknown') {
    return (
      <div className={[styles.toast, styles.error, styles[placement]].join(' ')} role="alert">
        <span className={shared.iconWithLabel}>
          <IconError aria-hidden="true" />
          <span>{ERROR_COPY.unknownEnum('toast severity', 'unknown')}</span>
        </span>
      </div>
    );
  }

  const Icon =
    severity === 'success'
      ? IconSuccess
      : severity === 'warning'
        ? IconWarning
        : severity === 'info'
          ? IconInfo
          : IconError;

  const resolved = message ?? DEFAULT_MESSAGES[severity];

  return (
    <div
      className={[styles.toast, styles[severity], styles[placement]].join(' ')}
      role={severity === 'error' ? 'alert' : 'status'}
      aria-live={severity === 'error' ? 'assertive' : 'polite'}
      data-toast-severity={severity}
    >
      <div className={styles.toastBody}>
        <span className={shared.iconWithLabel}>
          <Icon aria-hidden="true" />
          <span>{resolved}</span>
        </span>
        <button
          ref={dismissRef}
          type="button"
          className={[styles.dismiss, shared.focusVisible].join(' ')}
          aria-label="Dismiss notification"
          onClick={() => {
            onDismiss?.();
          }}
        >
          ×
        </button>
      </div>
      {showProgress && severity !== 'error' ? (
        <div
          className={styles.progressTrack}
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={progress | 0}
        >
          <span className={styles.progressBar} style={{ width: `${progress}%` }} />
        </div>
      ) : null}
    </div>
  );
}
