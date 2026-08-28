import { useCallback, useEffect, useRef, useState } from 'react';
import { getAuthState } from '../../../auth/sessionStore';
import { getDefaultExceptionDetailClient } from '../../../exceptions/exceptionDetailClient';
import {
  EXCEPTION_DETAIL_DRAWER_COPY,
  formatExceptionDetailToken,
  formatShortExceptionRef,
} from '../../../exceptions/copy';
import { ExceptionActionControls } from '../../../actions/ExceptionActionControls';
import type { ExceptionDetailDTO } from '../../../detail/types';
import { ERROR_COPY, LOADING_COPY } from '../../../lib/copy';
import { TimedLoadingPanel } from '../../../lib/loading/TimedLoadingPanel';
import { Modal } from '../../layout/Modal/Modal';
import { ErrorBanner } from '../../layout/ErrorBanner/ErrorBanner';
import { COMMAND_CENTER_POLICY_CHIP_PROPS } from '../../../commandCenter/commandCenterChipProps';
import { PolicyAuthorityPill } from '../../trust/PolicyAuthorityPill/PolicyAuthorityPill';
import shared from '../../../styles/shared.module.css';
import styles from './ExceptionDetailModal.module.css';

export interface ExceptionDetailModalProps {
  exceptionId: string | null;
  open: boolean;
  onClose: () => void;
  triggerRef?: React.RefObject<HTMLElement | null>;
}

/** @deprecated Use ExceptionDetailModal — retained for import / scan stability. */
export type ExceptionDetailDrawerProps = ExceptionDetailModalProps;

function ExceptionDetailBody({ detail }: { detail: ExceptionDetailDTO }) {
  const meta = [
    { label: EXCEPTION_DETAIL_DRAWER_COPY.category, value: formatExceptionDetailToken(detail.category) },
    { label: EXCEPTION_DETAIL_DRAWER_COPY.severity, value: formatExceptionDetailToken(detail.severity) },
    { label: EXCEPTION_DETAIL_DRAWER_COPY.affectedObject, value: detail.affectedObject },
    {
      label: EXCEPTION_DETAIL_DRAWER_COPY.reviewState,
      value: formatExceptionDetailToken(detail.reviewState),
    },
    { label: EXCEPTION_DETAIL_DRAWER_COPY.auditReference, value: detail.auditReference },
  ] as const;

  return (
    <>
      <section
        className={styles.issue}
        aria-label={detail.exceptionId}
        data-exception-detail-issue
      >
        <div className={styles.body}>
          <div className={styles.pillRow}>
            <PolicyAuthorityPill state={detail.policyAuthority} {...COMMAND_CENTER_POLICY_CHIP_PROPS} appearance="text" />
            <span className={styles.severityMark} data-exception-detail-severity={detail.severity}>
              {formatExceptionDetailToken(detail.severity)}
            </span>
          </div>
          <strong className={styles.title}>{formatExceptionDetailToken(detail.category)}</strong>
          <p className={styles.explanation}>{detail.evidenceSummary}</p>
        </div>
      </section>

      <dl className={styles.meta}>
        {meta.map((row) => (
          <div key={row.label} className={styles.metaRow}>
            <dt className={styles.metaLabel}>{row.label}</dt>
            <dd className={styles.metaValue}>{row.value}</dd>
          </div>
        ))}
      </dl>

      <section className={styles.review} aria-labelledby="exception-next-review-heading">
        <h3 id="exception-next-review-heading" className={styles.reviewHeading}>
          {EXCEPTION_DETAIL_DRAWER_COPY.recommendedNextReview}
        </h3>
        <ol className={styles.reviewList}>
          {detail.recommendedNextReview.map((item) => (
            <li key={item} className={styles.reviewItem}>
              {item}
            </li>
          ))}
        </ol>
      </section>

      <div className={styles.actions} aria-label={EXCEPTION_DETAIL_DRAWER_COPY.actions}>
        <ExceptionActionControls
          exceptionId={detail.exceptionId}
          versionStamp={detail.versionStamp}
          policyAuthority={detail.policyAuthority}
        />
      </div>
    </>
  );
}

export function ExceptionDetailModal({
  exceptionId,
  open,
  onClose,
  triggerRef,
}: ExceptionDetailModalProps) {
  const [detail, setDetail] = useState<ExceptionDetailDTO | null>(null);
  const [error, setError] = useState<string>();
  const [loading, setLoading] = useState(false);
  const activeRef = useRef(0);

  const load = useCallback(async () => {
    if (!open) return;
    if (!exceptionId) {
      setDetail(null);
      setLoading(false);
      setError(ERROR_COPY.missingRequiredProp('exceptionId'));
      return;
    }
    const requestId = ++activeRef.current;
    setLoading(true);
    setError(undefined);
    setDetail(null);
    const { tenant } = getAuthState();
    const outcome = await getDefaultExceptionDetailClient().getExceptionDetail(
      tenant?.tenantId ?? '',
      exceptionId,
    );
    if (activeRef.current !== requestId) return;
    setLoading(false);
    if (outcome.kind === 'loaded') setDetail(outcome.detail);
    else setError(outcome.message);
  }, [exceptionId, open]);

  useEffect(() => {
    void load();
  }, [load]);

  const title = exceptionId ? (
    <>
      <span className={styles.titlePrimary}>{EXCEPTION_DETAIL_DRAWER_COPY.titlePrimary}</span>
      <span
        className={styles.titleRef}
        data-exception-detail-title-ref
        title={exceptionId}
      >
        #{formatShortExceptionRef(exceptionId)}
      </span>
    </>
  ) : (
    EXCEPTION_DETAIL_DRAWER_COPY.titleFallback
  );

  return (
    <Modal
      open={open}
      onClose={onClose}
      triggerRef={triggerRef}
      title={title}
      size="wide"
      closeOnBackdropClick
    >
      <div
        className={styles.root}
        data-exception-detail-modal
        data-exception-detail-drawer
      >
        <TimedLoadingPanel
          active={loading}
          progressCopy={EXCEPTION_DETAIL_DRAWER_COPY.loading}
          onRetry={load}
          skeletonRows={4}
          skeletonVariant="text"
        />
        {!loading && error ? (
          <div className={styles.errorBlock}>
            <ErrorBanner variant="error" message={error} />
            <button
              type="button"
              className={[styles.retry, shared.focusVisible].join(' ')}
              onClick={() => void load()}
            >
              {LOADING_COPY.retry}
            </button>
          </div>
        ) : null}
        {!loading && !error && detail ? <ExceptionDetailBody detail={detail} /> : null}
      </div>
    </Modal>
  );
}

/** @deprecated Prefer ExceptionDetailModal */
export const ExceptionDetailDrawer = ExceptionDetailModal;
