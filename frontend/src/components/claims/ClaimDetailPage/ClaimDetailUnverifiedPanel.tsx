import { useState } from 'react';
import { getAuthState } from '../../../auth/sessionStore';
import { CLAIM_DETAIL_COPY } from '../../../claims/claimDetailCopy';
import { formatClaimDetailTitle } from '../../../claims/claimDetailDisplay';
import { getDefaultExcludeFromBudgetClient } from '../../../claims/excludeFromBudgetClient';
import { claimSourceLabel } from '../../../claims/claimsLedgerDisplay';
import shared from '../../../styles/shared.module.css';
import styles from './ClaimDetailPage.module.css';

export interface ClaimDetailUnverifiedPanelProps {
  claimId: string;
  claimSource: string;
  claimRef: string;
}

export function ClaimDetailUnverifiedPanel({
  claimId,
  claimSource,
  claimRef,
}: ClaimDetailUnverifiedPanelProps) {
  const { tenant } = getAuthState();
  const [status, setStatus] = useState<'idle' | 'pending' | 'success' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const title = formatClaimDetailTitle(claimSource, claimRef);
  const platform = claimSourceLabel(claimSource);

  const onExclude = async () => {
    setStatus('pending');
    setErrorMessage(null);
    const outcome = await getDefaultExcludeFromBudgetClient().excludeClaim(
      tenant?.tenantId ?? '',
      claimId,
    );
    if (outcome.kind === 'success') {
      setStatus('success');
      return;
    }
    setStatus('error');
    setErrorMessage(outcome.message || CLAIM_DETAIL_COPY.unverified.excludeError);
  };

  return (
    <section
      className={styles.unverifiedSection}
      aria-labelledby="claim-unverified-heading"
      data-claim-unverified-panel
    >
      <p className={styles.platformEyebrow}>{platform}</p>
      <h1 id="claim-unverified-heading" className={styles.unverifiedTitle} title={claimRef}>
        {title}
      </h1>
      <p className={styles.unverifiedMessage} role="status" data-claim-unverified-message>
        {CLAIM_DETAIL_COPY.unverified.message}
      </p>
      <p className={styles.unverifiedSupport}>{CLAIM_DETAIL_COPY.unverified.support}</p>
      <button
        type="button"
        className={[styles.excludeButton, shared.focusVisible].join(' ')}
        data-claim-exclude-budget
        disabled={status === 'pending' || status === 'success'}
        onClick={() => {
          void onExclude();
        }}
      >
        {CLAIM_DETAIL_COPY.unverified.excludeButton}
      </button>
      {status === 'success' ? (
        <p className={styles.excludeFeedback} role="status" data-claim-exclude-status="success">
          {CLAIM_DETAIL_COPY.unverified.excludeSuccess}
        </p>
      ) : null}
      {status === 'error' ? (
        <p className={styles.excludeError} role="alert" data-claim-exclude-status="error">
          {errorMessage}
        </p>
      ) : null}
    </section>
  );
}
