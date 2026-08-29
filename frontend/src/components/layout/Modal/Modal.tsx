import { useEffect, useId, useRef, type ReactNode } from 'react';
import { ERROR_COPY } from '../../../lib/copy';
import shared from '../../../styles/shared.module.css';
import styles from './Modal.module.css';

export type ModalType = 'standard' | 'destructive' | 'unknown';
export type ModalSize = 'standard' | 'wide';

export interface ModalProps {
  open: boolean;
  onClose: () => void;
  triggerRef?: React.RefObject<HTMLElement | null>;
  /** Accessible title; may be a string or structured nodes (e.g. primary + titleRef). */
  title: ReactNode;
  children?: ReactNode;
  type?: ModalType;
  size?: ModalSize;
  closeOnBackdropClick?: boolean;
  confirmLabel?: string;
  onConfirm?: () => void;
}

export function Modal({
  open,
  onClose,
  triggerRef,
  title,
  children,
  type = 'standard',
  size = 'standard',
  closeOnBackdropClick = false,
  confirmLabel = 'Confirm',
  onConfirm,
}: ModalProps) {
  const titleId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (open) {
      previousFocus.current = (triggerRef?.current ?? document.activeElement) as HTMLElement | null;
      dialogRef.current?.focus();
    } else if (previousFocus.current) {
      previousFocus.current.focus();
    }
  }, [open, triggerRef]);

  useEffect(() => {
    if (!open) return;

    const onKey = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      if (type === 'destructive') return;
      onClose();
    };

    const trapFocus = (event: KeyboardEvent) => {
      if (event.key !== 'Tab' || !dialogRef.current) return;
      const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      );
      if (!focusable.length) return;
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

    window.addEventListener('keydown', onKey);
    window.addEventListener('keydown', trapFocus);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('keydown', trapFocus);
    };
  }, [open, onClose, type]);

  if (!open) return null;

  if (type === 'unknown') {
    return (
      <div className={shared.errorState} role="alert">
        {ERROR_COPY.unknownEnum('modal type', 'unknown')}
      </div>
    );
  }

  if (title == null || title === '') {
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
        data-modal-backdrop
        onClick={closeOnBackdropClick ? onClose : undefined}
      />
      <div
        ref={dialogRef}
        className={[styles.modal, size === 'wide' ? styles.wide : '', styles.animate].filter(Boolean).join(' ')}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        data-modal-panel
      >
        <header className={styles.header}>
          <h2 id={titleId} className={styles.title}>
            {title}
          </h2>
          {type === 'standard' ? (
            <button
              type="button"
              className={[styles.close, shared.focusVisible].join(' ')}
              aria-label="Close modal"
              onClick={onClose}
            >
              ×
            </button>
          ) : null}
        </header>
        <div className={styles.body}>{children}</div>
        {type === 'destructive' && onConfirm ? (
          <footer className={styles.footer}>
            <button type="button" className={[styles.secondary, shared.focusVisible].join(' ')} onClick={onClose}>
              Cancel
            </button>
            <button type="button" className={[styles.destructive, shared.focusVisible].join(' ')} onClick={onConfirm}>
              {confirmLabel}
            </button>
          </footer>
        ) : null}
      </div>
    </>
  );
}
