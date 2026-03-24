import React from 'react';
import '../../budget-shared.css';

export type ButtonVariant = 'primary' | 'secondary' | 'tertiary' | 'ghost' | 'success' | 'danger' | 'error';
export type ButtonSize = 'default' | 'small' | 'sm' | 'lg' | 'large';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  fullWidth?: boolean;
  isLoading?: boolean;
  icon?: React.ReactNode;
  children?: React.ReactNode;
}

export function Button({
  variant = 'secondary',
  size = 'default',
  fullWidth = false,
  isLoading = false,
  icon,
  children,
  className = '',
  disabled,
  ...props
}: ButtonProps) {
  const variantClass =
    variant === 'primary' ? 'bud-btn--primary'
    : variant === 'secondary' ? 'bud-btn--secondary'
    : variant === 'tertiary' ? 'bud-btn--tertiary'
    : variant === 'ghost' ? 'bud-btn--ghost'
    : variant === 'success' ? 'bud-btn--success'
    : (variant === 'danger' || variant === 'error') ? 'bud-btn--danger'
    : 'bud-btn--secondary';

  const sizeClass =
    size === 'sm' || size === 'small' ? 'bud-btn--sm'
    : size === 'lg' || size === 'large' ? 'bud-btn--lg'
    : '';

  const classes = [
    'bud-btn',
    variantClass,
    sizeClass,
    fullWidth ? 'bud-btn--full' : '',
    className,
  ].filter(Boolean).join(' ');

  return (
    <button className={classes} disabled={disabled || isLoading} {...props}>
      {isLoading ? (
        <span className={`bud-spinner ${variant === 'secondary' || variant === 'tertiary' || variant === 'ghost' ? 'bud-spinner--dark' : ''}`} />
      ) : icon ? (
        icon
      ) : null}
      {children}
    </button>
  );
}
