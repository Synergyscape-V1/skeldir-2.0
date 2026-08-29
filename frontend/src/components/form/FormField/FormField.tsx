import type { InputHTMLAttributes } from 'react';
import styles from './FormField.module.css';

export interface FormFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'id'> {
  id: string;
  label: string;
  error?: string;
  hint?: string;
  describedByExtra?: string;
}

export function FormField({
  id,
  label,
  error,
  hint,
  describedByExtra,
  className,
  disabled,
  ...inputProps
}: FormFieldProps) {
  const errorId = error ? `${id}-error` : undefined;
  const hintId = hint ? `${id}-hint` : undefined;
  const describedBy = [errorId, hintId, describedByExtra].filter(Boolean).join(' ') || undefined;

  return (
    <div className={[styles.field, disabled ? styles.disabled : ''].join(' ')}>
      <label className={styles.label} htmlFor={id}>
        {label}
      </label>
      <input
        id={id}
        className={[styles.input, error ? styles.inputInvalid : '', className ?? ''].join(' ')}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        disabled={disabled}
        {...inputProps}
      />
      {hint ? (
        <p id={hintId} className={styles.hint}>
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} className={styles.error} role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
