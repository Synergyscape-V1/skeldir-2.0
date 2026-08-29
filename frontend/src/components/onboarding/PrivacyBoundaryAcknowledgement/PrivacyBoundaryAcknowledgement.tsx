import shared from '../../../styles/shared.module.css';
import { ACTIVATION_COPY } from '../../../activation/copy';
import styles from './PrivacyBoundaryAcknowledgement.module.css';

export interface PrivacyBoundaryAcknowledgementProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  id?: string;
}

export function PrivacyBoundaryAcknowledgement({
  checked,
  onChange,
  disabled = false,
  id = 'privacy-boundary-ack',
}: PrivacyBoundaryAcknowledgementProps) {
  return (
    <div className={styles.acknowledgement} data-privacy-acknowledgement>
      <input
        id={id}
        type="checkbox"
        className={[styles.checkbox, shared.focusVisible].join(' ')}
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
        aria-describedby={`${id}-boundary-copy`}
      />
      <label
        htmlFor={id}
        className={[styles.label, disabled ? styles.disabled : ''].filter(Boolean).join(' ')}
      >
        {ACTIVATION_COPY.step4.acknowledgementLabel}
      </label>
    </div>
  );
}
