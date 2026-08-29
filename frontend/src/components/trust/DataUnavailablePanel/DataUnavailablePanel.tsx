import { ERROR_COPY, UNAVAILABLE_COPY, LOADING_COPY } from '../../../lib/copy';
import { POLICY_AUTHORITY_EXPLANATION } from '../../../lib/policyAuthorityLabels';
import type { UnavailableVariant } from '../../../lib/types';
import { AuthorityBadge } from '../AuthorityBadge/AuthorityBadge';
import { Skeleton } from '../../layout/Skeleton/Skeleton';
import shared from '../../../styles/shared.module.css';
import styles from './DataUnavailablePanel.module.css';

export interface DataUnavailablePanelProps {
  reason?: string;
  whatStillWorks?: string;
  nextEligibleAt?: string;
  userAction?: {
    label: string;
    onClick: () => void;
    disabled?: boolean;
  };
  variant?: UnavailableVariant;
  loading?: boolean;
  loadingPhase?: 'under_2s' | 'over_2s';
}

const VARIANT_COPY: Record<UnavailableVariant, { title: string; defaultReason?: string }> = {
  default: { title: UNAVAILABLE_COPY.default },
  no_confidence: { title: UNAVAILABLE_COPY.noConfidence },
  no_benchmark: { title: UNAVAILABLE_COPY.noBenchmark },
  no_commerce_truth: { title: UNAVAILABLE_COPY.noCommerceTruth },
  no_platform_claims: { title: UNAVAILABLE_COPY.noPlatformClaims },
  suppressed: { title: 'Data suppressed for this segment.', defaultReason: 'suppressed' },
  sparse_data: {
    title: 'Insufficient data for this operation.',
    defaultReason: 'sparse_data',
  },
  partial_data: {
    title: UNAVAILABLE_COPY.default,
    defaultReason: 'partial_data',
  },
  blocked_simulation: {
    title: POLICY_AUTHORITY_EXPLANATION.blockedSparse,
    defaultReason: 'LP_INPUT_MATRIX_UNDERDETERMINED',
  },
};

export function DataUnavailablePanel({
  reason,
  whatStillWorks,
  nextEligibleAt,
  userAction,
  variant = 'default',
  loading,
  loadingPhase = 'under_2s',
}: DataUnavailablePanelProps) {
  if (loading) {
    return (
      <div className={styles.panel} aria-busy="true">
        <Skeleton rows={2} />
        {loadingPhase === 'over_2s' ? (
          <p className={styles.progress} aria-live="polite" role="status">
            {LOADING_COPY.progress}
          </p>
        ) : null}
      </div>
    );
  }

  if (!reason && variant === 'default') {
    return (
      <div className={shared.errorState} role="alert">
        {ERROR_COPY.missingRequiredProp('reason')}
      </div>
    );
  }

  const variantConfig = VARIANT_COPY[variant] ?? VARIANT_COPY.default;
  const displayReason = reason ?? variantConfig.defaultReason ?? variantConfig.title;

  return (
    <div
      className={styles.panel}
      role="region"
      aria-label={`Unavailable data: ${variant}`}
      aria-live="polite"
    >
      {variant === 'suppressed' ? (
        <div className={styles.authorityRow}>
          <AuthorityBadge authority="suppressed" />
        </div>
      ) : null}
      <p className={styles.title}>{variantConfig.title}</p>
      {displayReason !== variantConfig.title ? (
        <p className={styles.reason}>{displayReason}</p>
      ) : null}
      {whatStillWorks ? <p className={styles.meta}>{whatStillWorks}</p> : null}
      {nextEligibleAt ? (
        <p className={styles.meta}>
          Next eligible: <time>{nextEligibleAt}</time>
        </p>
      ) : null}
      {userAction ? (
        <button
          type="button"
          className={[styles.action, shared.focusVisible].join(' ')}
          onClick={userAction.onClick}
          disabled={userAction.disabled}
        >
          {userAction.label}
        </button>
      ) : null}
    </div>
  );
}
