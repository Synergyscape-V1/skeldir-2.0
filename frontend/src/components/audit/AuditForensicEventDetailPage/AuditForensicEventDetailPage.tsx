import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { PageSurface } from '../../layout/PageSurface/PageSurface';
import { Typography } from '../../layout/Typography/Typography';
import { OPERATIONAL_AUDIT_COPY } from '../../../operationalAudit/copy';
import {
  formatForensicExecutiveActivityLabel,
  formatForensicTimestampUtc,
  resolveForensicChainVerification,
} from '../../../operationalAudit/forensicExecutiveDisplay';
import { resolveForensicBusinessDetail } from '../../../operationalAudit/forensicBusinessDetail';
import { useAuditLedger } from '../../../operationalAudit/useOperationalAudit';
import {
  ForensicChainVerificationBadge,
  ForensicExecutiveStatusCell,
} from '../ForensicExecutiveCells/ForensicExecutiveCells';
import { AuditArtifactDrawer } from '../AuditArtifactDrawer/AuditArtifactDrawer';
import { ErrorBanner } from '../../layout/ErrorBanner/ErrorBanner';
import { PermissionDeniedPanel } from '../../governance/PermissionDeniedPanel/PermissionDeniedPanel';
import shared from '../../../styles/shared.module.css';
import styles from './AuditForensicEventDetailPage.module.css';

export function AuditForensicEventDetailPage() {
  const { eventId = '' } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const {
    events,
    loading,
    error,
    permissionDenied,
    filteredEmpty,
    refresh,
  } = useAuditLedger(`?log=forensic&eventId=${encodeURIComponent(eventId)}`);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const triggerRef = useRef<HTMLElement | null>(null);

  const event = useMemo(
    () => events.find((entry) => entry.eventId === eventId),
    [events, eventId],
  );

  const businessDetail = useMemo(
    () => (event ? resolveForensicBusinessDetail(event) : null),
    [event],
  );

  useEffect(() => {
    if (searchParams.get('technical') === 'true' && event) {
      setDrawerOpen(true);
    }
  }, [event, searchParams]);

  const openTechnicalDrawer = useCallback(() => {
    triggerRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setDrawerOpen(true);
  }, []);

  const closeTechnicalDrawer = useCallback(() => {
    setDrawerOpen(false);
  }, []);

  if (!loading && permissionDenied) {
    return (
      <PageSurface data-audit-forensic-detail-page data-audit-forensic-detail-permission-denied>
        <PermissionDeniedPanel />
      </PageSurface>
    );
  }

  if (!loading && error) {
    return (
      <PageSurface data-audit-forensic-detail-page data-audit-forensic-detail-error>
        <ErrorBanner
          variant="error"
          message={OPERATIONAL_AUDIT_COPY.forensicEventLoadFailed}
          detail={error}
          action={
            <button
              type="button"
              className={[styles.retryAction, shared.focusVisible].join(' ')}
              onClick={() => void refresh()}
            >
              {OPERATIONAL_AUDIT_COPY.retryForensicEvent}
            </button>
          }
        />
      </PageSurface>
    );
  }

  if (!loading && filteredEmpty && !event) {
    return (
      <PageSurface data-audit-forensic-detail-page data-audit-forensic-detail-missing>
        <nav className={styles.breadcrumb} aria-label="Breadcrumb">
          <Link to="/app/audit?log=forensic">
            {OPERATIONAL_AUDIT_COPY.forensicBusinessDetail.breadcrumbLedger}
          </Link>
          <span aria-hidden="true">›</span>
          <span aria-current="page">{OPERATIONAL_AUDIT_COPY.forensicEventNotFoundTitle}</span>
        </nav>
        <header className={styles.header}>
          <Typography variant="h2">{OPERATIONAL_AUDIT_COPY.forensicEventNotFoundTitle}</Typography>
          <p className={styles.missingReference}>
            Audit reference <code>{eventId}</code>
          </p>
        </header>
        <div className={styles.missingPanel}>
          <ErrorBanner
            variant="error"
            message={OPERATIONAL_AUDIT_COPY.forensicEventNotFoundReason(eventId)}
            detail={OPERATIONAL_AUDIT_COPY.forensicEventNotFoundBoundary}
          />
          <Link
            to="/app/audit?log=forensic"
            className={[styles.missingAction, shared.focusVisible].join(' ')}
          >
            {OPERATIONAL_AUDIT_COPY.returnToForensicLedger}
          </Link>
        </div>
      </PageSurface>
    );
  }

  return (
    <PageSurface data-audit-forensic-detail-page data-audit-forensic-detail-loaded>
      <nav className={styles.breadcrumb} aria-label="Breadcrumb">
        <Link to="/app/audit?log=forensic">{OPERATIONAL_AUDIT_COPY.forensicBusinessDetail.breadcrumbLedger}</Link>
        <span aria-hidden="true">›</span>
        <span>{event ? formatForensicExecutiveActivityLabel(event.eventType) : 'Loading…'}</span>
        {event ? (
          <>
            <span aria-hidden="true">›</span>
            <span>{event.businessSubjectLabel ?? event.subjectLabel}</span>
          </>
        ) : null}
      </nav>

      <header className={styles.header}>
        <Typography variant="h2">{businessDetail?.headline ?? 'Forensic audit event'}</Typography>
        {event ? (
          <p className={styles.meta}>
            <time dateTime={event.occurredAt}>{formatForensicTimestampUtc(event.occurredAt)}</time>
          </p>
        ) : null}
      </header>

      {event ? (
        <section className={styles.summaryPanel} aria-label="Executive summary">
          <p>{businessDetail?.summary}</p>
          <div className={styles.signalRow}>
            <ForensicExecutiveStatusCell row={event} />
            <ForensicChainVerificationBadge status={resolveForensicChainVerification(event)} />
          </div>
          {businessDetail?.primaryActionHref ? (
            <Link
              to={businessDetail.primaryActionHref}
              className={[styles.primaryAction, shared.focusVisible].join(' ')}
              data-forensic-business-action
            >
              {businessDetail.primaryActionLabel}
            </Link>
          ) : null}
        </section>
      ) : (
        <p aria-busy="true">Loading forensic event…</p>
      )}

      <div className={styles.toolbar}>
        <button
          type="button"
          className={[styles.technicalButton, shared.focusVisible].join(' ')}
          data-view-technical-details
          onClick={openTechnicalDrawer}
          disabled={!event}
        >
          {OPERATIONAL_AUDIT_COPY.viewTechnicalDetails}
        </button>
        <button
          type="button"
          className={[styles.backButton, shared.focusVisible].join(' ')}
          onClick={() => navigate('/app/audit?log=forensic')}
        >
          Back to Audit Ledger
        </button>
      </div>

      <AuditArtifactDrawer
        eventId={event?.eventId ?? null}
        open={drawerOpen}
        onClose={closeTechnicalDrawer}
        triggerRef={triggerRef}
        timelineEvents={events}
        variant="technical"
      />
    </PageSurface>
  );
}
