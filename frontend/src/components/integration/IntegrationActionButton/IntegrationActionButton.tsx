import type { ButtonHTMLAttributes } from 'react';
import shared from '../../../styles/shared.module.css';
import { INTEGRATION_COPY } from '../../../integration/copy';
import styles from './IntegrationActionButton.module.css';

export interface IntegrationActionButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  action: 'connect' | 'repair';
  loading?: boolean;
  variant?: 'primary' | 'secondary';
}

export function IntegrationActionButton({
  action,
  loading = false,
  variant = 'primary',
  disabled,
  children,
  ...props
}: IntegrationActionButtonProps) {
  const defaultLabel = action === 'connect' ? INTEGRATION_COPY.connect : INTEGRATION_COPY.repair;
  const loadingLabel = action === 'connect' ? INTEGRATION_COPY.connecting : INTEGRATION_COPY.repairing;
  const accessibleName = `${defaultLabel}${loading ? `, ${loadingLabel}` : ''}`;

  return (
    <button
      type="button"
      className={[
        variant === 'primary' ? styles.primary : styles.actionButton,
        shared.focusVisible,
      ]
        .filter(Boolean)
        .join(' ')}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      aria-label={accessibleName}
      {...props}
    >
      {loading ? loadingLabel : (children ?? defaultLabel)}
    </button>
  );
}
