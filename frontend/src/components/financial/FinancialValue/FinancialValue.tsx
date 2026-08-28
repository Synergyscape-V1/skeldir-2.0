import type { AuthorityClass } from '../../../lib/types';
import { AuthorityBadge } from '../../trust/AuthorityBadge/AuthorityBadge';
import { ERROR_COPY } from '../../../lib/copy';
import {
  formatMoneyMinorDisplay,
  isKnownAuthority,
  isValidIsoCurrencyCode,
  parseMoneyMinor,
} from '../../../lib/money';
import shared from '../../../styles/shared.module.css';
import styles from './FinancialValue.module.css';

export interface FinancialValueProps {
  amountMinor?: bigint | string | null;
  currencyCode?: string;
  authority?: AuthorityClass | string;
  label?: string;
  unavailableReason?: string;
}

export function FinancialValue({
  amountMinor,
  currencyCode,
  authority,
  label,
  unavailableReason,
}: FinancialValueProps) {
  if (amountMinor === null || amountMinor === undefined) {
    if (!unavailableReason) {
      return (
        <div className={shared.errorState} role="alert">
          {ERROR_COPY.missingRequiredProp('unavailableReason when amountMinor is null')}
        </div>
      );
    }
    return (
      <div className={styles.unavailable} role="status">
        <span className={styles.label}>{label ?? 'Verified revenue'}</span>
        <p className={styles.reason}>{unavailableReason}</p>
        <AuthorityBadge authority="unavailable" />
      </div>
    );
  }

  if (!currencyCode || !isValidIsoCurrencyCode(currencyCode)) {
    return (
      <div className={shared.errorState} role="alert">
        {ERROR_COPY.missingRequiredProp('valid ISO currencyCode')}
      </div>
    );
  }

  if (!authority || !isKnownAuthority(authority)) {
    return (
      <div className={shared.errorState} role="alert">
        {authority
          ? ERROR_COPY.invalidAuthorityState
          : ERROR_COPY.missingRequiredProp('authority')}
      </div>
    );
  }

  const parsed = parseMoneyMinor(amountMinor);
  if (!parsed.ok) {
    return (
      <div className={shared.errorState} role="alert">
        {parsed.error}
      </div>
    );
  }

  const display = formatMoneyMinorDisplay(parsed.value, currencyCode);

  return (
    <div className={styles.valueRow} role="group" aria-label={label ?? 'Financial value'}>
      {label ? <span className={styles.label}>{label}</span> : null}
      <span className={styles.amount} data-field="amount_minor" title={`${parsed.value.toString()} minor units`}>
        {display}
      </span>
      <AuthorityBadge authority={authority as AuthorityClass} />
    </div>
  );
}
