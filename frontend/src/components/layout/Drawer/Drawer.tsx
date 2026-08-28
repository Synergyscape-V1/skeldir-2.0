import { useEffect, useId, useRef, type ReactNode } from 'react';
import { ERROR_COPY, LOADING_COPY } from '../../../lib/copy';
import { useTimedLoading } from '../../../lib/loading';
import { ErrorBanner } from '../ErrorBanner/ErrorBanner';
import { Skeleton } from '../Skeleton/Skeleton';
import shared from '../../../styles/shared.module.css';
import styles from './Drawer.module.css';

export type DrawerState = 'closed' | 'opening' | 'open' | 'loading' | 'error';
export type DrawerSize = 'standard' | 'wide';

export interface DrawerProps {
  open: boolean;
  onClose: () => void;
  triggerRef?: React.RefObject<HTMLElement | null>;
  title: string;
  children?: ReactNode;
  footer?: ReactNode;
  state?: DrawerState;
  progressCopy?: string;
  errorMessage?: string;
  onRetry?: () => void;
  position?: 'right' | 'left' | 'unknown';
  size?: DrawerSize;
  allowEscape?: boolean;
  closeOnBackdropClick?: boolean;
}

const FOCUSABLE_SELECTOR =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

function getFocusableElements(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter(
    (el) => !el.hasAttribute('disabled') && el.getAttribute('aria-hidden') !== 'true',
  );
}

export function Drawer({
  open,
  onClose,
  triggerRef,
  title,
  children,
  footer,
  state = 'open',
  progressCopy,
  errorMessage,
  onRetry,
  position = 'right',
  size = 'standard',
  allowEscape = true,
  closeOnBackdropClick = true,
}: DrawerProps) {
  const titleId = useId();
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const drawerRef = useRef<HTMLDivElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  const loadingPhase = useTimedLoading(state === 'loading');
  const resolvedProgressCopy = progressCopy ?? LOADING_COPY.progress;

  useEffect(() => {
    if (open) {
      previousFocus.current = (triggerRef?.current ?? document.activeElement) as HTMLElement | null;
      closeButtonRef.current?.focus();
    } else if (previousFocus.current) {
      previousFocus.current.focus();
    }
  }, [open, triggerRef]);

  useEffect(() => {
    if (!open || !allowEscape) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, allowEscape, onClose]);

  useEffect(() => {
    if (!open) return;

    const trapFocus = (event: KeyboardEvent) => {
      if (event.key !== 'Tab' || !drawerRef.current) return;
      const focusable = getFocusableElements(drawerRef.current);
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    window.addEventListener('keydown', trapFocus);
    return () => window.removeEventListener('keydown', trapFocus);
  }, [open]);

  if (!open) return null;

  if (position === 'unknown') {
    return (
      <div className={shared.errorState} role="alert">
        {ERROR_COPY.unknownEnum('drawer position', 'unknown')}
      </div>
    );
  }

  if (!title) {
    return (
      <div className={shared.errorState} role="alert">
        {ERROR_COPY.missingRequiredProp('title')}
      </div>
    );
  }

  return (
    <>
      <div
        className={styles.backdrop}
        aria-hidden="true"
        data-drawer-backdrop
        onClick={closeOnBackdropClick ? onClose : undefined}
      />
      <div
        ref={drawerRef}
        className={[
          styles.drawer,
          styles[position],
          size === 'wide' ? styles.wide : '',
          styles.animate,
        ]
          .filter(Boolean)
          .join(' ')}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        data-drawer-panel
        data-drawer-size={size}
      >
        <header className={styles.header}>
          <h2 id={titleId} className={styles.title}>
            {title}
          </h2>
          <button
            ref={closeButtonRef}
            type="button"
            className={[styles.close, shared.focusVisible].join(' ')}
            aria-label="Close drawer"
            onClick={onClose}
          >
            ×
          </button>
        </header>
        <div className={styles.body}>
          {state === 'loading' ? <Skeleton rows={4} variant="text" /> : null}
          {state === 'loading' && (loadingPhase === 'over_2s' || loadingPhase === 'over_8s') ? (
            <p className={styles.progress} aria-live="polite" role="status">
              {resolvedProgressCopy}
            </p>
          ) : null}
          {state === 'loading' && loadingPhase === 'over_8s' && onRetry ? (
            <button type="button" className={[styles.retry, shared.focusVisible].join(' ')} onClick={onRetry}>
              {LOADING_COPY.retry}
            </button>
          ) : null}
          {state === 'error' ? (
            <ErrorBanner variant="error" message={errorMessage ?? ERROR_COPY.trustApiReadFailed} />
          ) : null}
          {(state === 'open' || state === 'opening') && children}
        </div>
        {footer ? <footer className={styles.footer}>{footer}</footer> : null}
      </div>
    </>
  );
}
