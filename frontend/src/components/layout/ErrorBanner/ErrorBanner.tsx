import type { ReactNode } from 'react';
import { IconError, IconInfo, IconSuccess, IconWarning } from '../../icons/StatusIcons';
import { ERROR_COPY } from '../../../lib/copy';
import shared from '../../../styles/shared.module.css';
import styles from './ErrorBanner.module.css';

export type ErrorBannerVariant = 'error' | 'warning' | 'info' | 'success' | 'permission_denied';

const VARIANT_COPY: Record<ErrorBannerVariant, string> = {
  error: ERROR_COPY.trustApiReadFailed,
  warning: 'Integration attention needed.',
  info: 'Information',
  success: 'Success',
  permission_denied: ERROR_COPY.permissionDenied,
};

export interface ErrorBannerProps {
  variant?: ErrorBannerVariant;
  message?: string;
  detail?: string;
  action?: ReactNode;
}

export function ErrorBanner({ variant = 'error', message, detail, action }: ErrorBannerProps) {
  if (!(variant in VARIANT_COPY)) {
    return (
      <div className={shared.errorState} role="alert">
        {ERROR_COPY.unknownEnum('error banner variant', String(variant))}
      </div>
    );
  }

  const Icon =
    variant === 'success'
      ? IconSuccess
      : variant === 'warning'
        ? IconWarning
        : variant === 'info'
          ? IconInfo
          : IconError;

  const resolvedMessage = message ?? VARIANT_COPY[variant];

  return (
    <div
      className={[styles.banner, styles[variant]].join(' ')}
      role={variant === 'error' || variant === 'permission_denied' ? 'alert' : 'status'}
      aria-live={variant === 'error' || variant === 'permission_denied' ? 'assertive' : 'polite'}
    >
      <span className={shared.iconWithLabel}>
        <Icon aria-hidden="true" />
        <span className={styles.label}>{resolvedMessage}</span>
      </span>
      {detail ? <p className={styles.detail}>{detail}</p> : null}
      {action}
    </div>
  );
}
