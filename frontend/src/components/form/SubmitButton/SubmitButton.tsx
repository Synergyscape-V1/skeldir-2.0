import type { ButtonHTMLAttributes } from 'react';
import styles from './SubmitButton.module.css';

export interface SubmitButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  loading?: boolean;
  loadingLabel?: string;
  variant?: 'primary' | 'secondary' | 'oauth';
}

export function SubmitButton({
  loading = false,
  loadingLabel = 'Submitting…',
  variant = 'primary',
  disabled,
  children,
  type = 'submit',
  ...props
}: SubmitButtonProps) {
  const isDisabled = disabled || loading;

  return (
    <button
      type={type}
      className={[styles.button, variant !== 'primary' ? styles[variant] : ''].join(' ')}
      disabled={isDisabled}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading ? loadingLabel : children}
    </button>
  );
}
