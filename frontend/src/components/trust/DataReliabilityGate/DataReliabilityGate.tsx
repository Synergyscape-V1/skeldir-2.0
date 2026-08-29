import { Link } from 'react-router-dom';
import { IconWarning } from '../../icons/StatusIcons';
import type { ExecutiveReliabilityResolution } from '../../../trust/executiveDataReliability';
import {
  EXECUTIVE_RELIABILITY_COPY,
  executiveReliabilityAlertBody,
  executiveReliabilityAlertHeadline,
} from '../../../trust/executiveDataReliabilityCopy';
import { ExecutiveReliabilityBadge } from '../ExecutiveReliabilityBadge/ExecutiveReliabilityBadge';
import shared from '../../../styles/shared.module.css';
import styles from './DataReliabilityGate.module.css';

export interface DataReliabilityGateProps {
  resolution: ExecutiveReliabilityResolution;
  amountDisplay: string;
  label?: string;
  showInlineAlert?: boolean;
  /** When false, omits ExecutiveReliabilityBadge (claim-detail declutter). Default true. */
  showReliabilityBadge?: boolean;
  repairHref?: string;
  variant?: 'hero' | 'compact';
}

export function DataReliabilityGate({
  resolution,
  amountDisplay,
  label,
  showInlineAlert = true,
  showReliabilityBadge = true,
  repairHref = EXECUTIVE_RELIABILITY_COPY.repairHref,
  variant = 'hero',
}: DataReliabilityGateProps) {
  const { reliability, variant: reliabilityVariant } = resolution;
  const alertHeadline = executiveReliabilityAlertHeadline(reliability, reliabilityVariant);
  const alertBody = executiveReliabilityAlertBody(reliability, reliabilityVariant);
  const isDiscrepancy = reliability === 'discrepancy';
  const valueClass = [
    styles.amount,
    reliability === 'verified' ? styles.amountVerified : '',
    reliability === 'estimated' ? styles.amountEstimated : '',
    reliability === 'pending' ? styles.amountPending : '',
    reliability === 'unavailable' ? styles.amountUnavailable : '',
    isDiscrepancy ? styles.amountDiscrepancy : '',
  ]
    .filter(Boolean)
    .join(' ');

  const showHeaderRow = Boolean(label) || showReliabilityBadge;

  return (
    <div
      className={[styles.gate, variant === 'compact' ? styles.compact : ''].filter(Boolean).join(' ')}
      data-data-reliability-gate={reliability}
      data-data-reliability-export-allowed={resolution.allowsVerifiedExport ? 'true' : 'false'}
      data-data-reliability-simulator-allowed={resolution.allowsSimulator ? 'true' : 'false'}
    >
      {showHeaderRow ? (
        <div className={styles.headerRow}>
          {label ? <span className={styles.label}>{label}</span> : null}
          {showReliabilityBadge ? (
            <ExecutiveReliabilityBadge reliability={reliability} variant={reliabilityVariant} />
          ) : null}
        </div>
      ) : null}

      <span
        className={valueClass}
        data-trust-envelope-verified-revenue={variant === 'hero' ? true : undefined}
        data-executive-revenue-display
      >
        {amountDisplay}
      </span>

      {showInlineAlert && alertHeadline && alertBody ? (
        <div
          className={[styles.alert, isDiscrepancy ? styles.alertDiscrepancy : ''].filter(Boolean).join(' ')}
          role="status"
          aria-live="polite"
          data-data-reliability-alert
          data-data-reliability-alert-tone={isDiscrepancy ? 'error' : 'warning'}
        >
          <div className={styles.alertTitleRow}>
            {!isDiscrepancy ? (
              <IconWarning
                aria-hidden="true"
                className={[styles.alertIcon, styles.alertIconWarning].filter(Boolean).join(' ')}
              />
            ) : null}
            <p
              className={[styles.alertHeadline, isDiscrepancy ? styles.alertHeadlineFootnote : '']
                .filter(Boolean)
                .join(' ')}
            >
              {alertHeadline}
            </p>
          </div>
          <p className={styles.alertBody}>{alertBody}</p>
          {reliability === 'estimated' ? (
            <Link
              to={repairHref}
              className={[styles.repairLink, shared.focusVisible].join(' ')}
              data-data-reliability-repair-link
            >
              {EXECUTIVE_RELIABILITY_COPY.repairLink}
            </Link>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export function dataReliabilityGateDisabledReason(
  _resolution: ExecutiveReliabilityResolution,
  action: 'simulator' | 'export',
): string {
  if (action === 'simulator') {
    return EXECUTIVE_RELIABILITY_COPY.permissions.simulatorBlocked;
  }
  return EXECUTIVE_RELIABILITY_COPY.permissions.exportBlocked;
}
