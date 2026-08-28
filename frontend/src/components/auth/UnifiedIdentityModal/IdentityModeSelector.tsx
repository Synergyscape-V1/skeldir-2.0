import type { IdentityMode } from '../../../auth/identityFlow';
import { AUTH_COPY } from '../../../auth/copy';
import styles from './UnifiedIdentityModal.module.css';

export interface IdentityModeSelectorProps {
  mode: IdentityMode;
  disabled?: boolean;
  onChange: (mode: IdentityMode) => void;
}

export function IdentityModeSelector({ mode, disabled = false, onChange }: IdentityModeSelectorProps) {
  return (
    <div
      className={styles.segmented}
      data-identity-mode-selector
      role="tablist"
      aria-label="Sign in or sign up"
    >
      <span className={styles.segmentIndicator} data-active={mode} aria-hidden="true" />
      <button
        type="button"
        role="tab"
        id="identity-mode-sign-in"
        className={styles.segment}
        aria-selected={mode === 'sign-in'}
        disabled={disabled}
        onClick={() => onChange('sign-in')}
      >
        {AUTH_COPY.submitLogin}
      </button>
      <button
        type="button"
        role="tab"
        id="identity-mode-sign-up"
        className={styles.segment}
        aria-selected={mode === 'sign-up'}
        disabled={disabled}
        onClick={() => onChange('sign-up')}
      >
        {AUTH_COPY.submitSignup}
      </button>
    </div>
  );
}
