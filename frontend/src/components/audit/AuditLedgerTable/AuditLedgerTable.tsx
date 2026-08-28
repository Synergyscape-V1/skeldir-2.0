import { useMemo } from 'react';
import { Table, type TableColumn, type TableCursorPagination } from '../../layout/Table/Table';
import { ERROR_COPY, LOADING_COPY } from '../../../lib/copy';
import { useTimedTableLoading } from '../../../lib/loading';
import { OPERATIONAL_AUDIT_COPY } from '../../../operationalAudit/copy';
import {
  formatForensicExecutiveActivityLabel,
  formatForensicExecutiveActor,
  formatForensicExecutiveSubject,
  formatForensicTimestampUtc,
  forensicActorTechnicalId,
  resolveForensicChainVerification,
} from '../../../operationalAudit/forensicExecutiveDisplay';
import type { AuditEvent, AuditLogMode } from '../../../operationalAudit/types';
import {
  ForensicChainVerificationBadge,
  ForensicExecutiveStatusCell,
} from '../ForensicExecutiveCells/ForensicExecutiveCells';
import styles from './AuditLedgerTable.module.css';

export interface AuditLedgerTableProps {
  logMode: AuditLogMode;
  events: AuditEvent[];
  loading?: boolean;
  loadingMore?: boolean;
  error?: string;
  permissionDenied?: boolean;
  empty?: boolean;
  filteredEmpty?: boolean;
  selectedEventId?: string | null;
  onOpenForensic?: (event: AuditEvent) => void;
  onClearFilters?: () => void;
  cursorPagination?: TableCursorPagination;
  onRetry?: () => void;
}

export function AuditLedgerTable({
  logMode,
  events,
  loading,
  loadingMore,
  error,
  permissionDenied,
  empty,
  filteredEmpty,
  selectedEventId,
  onOpenForensic,
  onClearFilters,
  cursorPagination,
  onRetry,
}: AuditLedgerTableProps) {
  const columns: TableColumn<AuditEvent>[] = useMemo(() => {
    if (logMode === 'forensic_log') {
      return [
        {
          key: 'when',
          header: 'When',
          render: (row) => (
            <time dateTime={row.occurredAt} data-forensic-when>
              {formatForensicTimestampUtc(row.occurredAt)}
            </time>
          ),
        },
        {
          key: 'activity',
          header: 'Activity',
          render: (row) => (
            <span
              data-audit-event-type={row.eventType}
              title={row.eventType}
              data-forensic-activity
            >
              {formatForensicExecutiveActivityLabel(row.eventType)}
            </span>
          ),
        },
        {
          key: 'who',
          header: 'Who',
          render: (row) => {
            const technicalId = forensicActorTechnicalId(row);
            return (
              <span title={technicalId} data-forensic-who>
                {formatForensicExecutiveActor(row)}
              </span>
            );
          },
        },
        {
          key: 'what',
          header: 'What',
          render: (row) => (
            <span title={row.subjectLabel} data-forensic-what>
              {formatForensicExecutiveSubject(row)}
            </span>
          ),
        },
        {
          key: 'status',
          header: 'Status',
          render: (row) => <ForensicExecutiveStatusCell row={row} />,
        },
        {
          key: 'verification',
          header: 'Verification',
          render: (row) => (
            <ForensicChainVerificationBadge status={resolveForensicChainVerification(row)} />
          ),
        },
      ];
    }

    return [
      {
        key: 'timestamp',
        header: 'Timestamp',
        render: (row) => formatForensicTimestampUtc(row.occurredAt),
      },
      {
        key: 'actor',
        header: 'Actor',
        render: (row) => row.actorLabel || ERROR_COPY.missingRequiredProp('actor'),
      },
      {
        key: 'endpoint',
        header: 'Endpoint',
        render: (row) => row.endpoint ?? ERROR_COPY.missingRequiredProp('endpoint'),
      },
      {
        key: 'target',
        header: 'Target',
        render: (row) => row.envelopeRef ?? row.subjectLabel,
      },
    ];
  }, [logMode]);

  const timedLoading = useTimedTableLoading(!!loading, {
    progressCopy: LOADING_COPY.progress,
    onRetry,
  });

  let state: import('../../layout/Table/Table').TableState = 'populated';
  if (permissionDenied) state = 'permission_denied';
  else if (error) state = 'error';
  else if (timedLoading) state = timedLoading.state;
  else if (filteredEmpty) state = 'filtered_empty';
  else if (empty) state = 'empty';

  const sectionTitle =
    logMode === 'forensic_log'
      ? OPERATIONAL_AUDIT_COPY.auditTableSectionTitleForensic
      : OPERATIONAL_AUDIT_COPY.auditTableSectionTitleAccess;

  const caption =
    logMode === 'forensic_log'
      ? OPERATIONAL_AUDIT_COPY.auditTableCaptionForensic
      : OPERATIONAL_AUDIT_COPY.auditTableCaptionAccess;

  const handleRowActivate =
    logMode === 'forensic_log' && onOpenForensic ? onOpenForensic : undefined;

  const tableHeadingId = 'audit-ledger-table-heading';

  return (
    <section
      className={styles.tableCard}
      data-audit-ledger-table
      data-audit-log-mode={logMode}
      aria-labelledby={tableHeadingId}
      {...(logMode === 'forensic_log' ? { 'data-audit-executive-table': true } : {})}
    >
      <div className={styles.tableHeader}>
        <div className={styles.tableHeading}>
          <h2 id={tableHeadingId} className={styles.sectionTitle}>
            {sectionTitle}
          </h2>
          <p className={styles.sectionSubtitle} data-audit-sort-locked>
            {OPERATIONAL_AUDIT_COPY.auditSortLockedNote}
          </p>
        </div>
      </div>
      <div className={styles.tableWrap}>
        <Table
          caption={caption}
          captionVisibility="visuallyHidden"
          columns={columns}
          rows={events}
          state={state}
          progressCopy={timedLoading?.progressCopy}
          onRetry={timedLoading?.onRetry}
          errorMessage={error}
          emptyTitle={OPERATIONAL_AUDIT_COPY.auditEmpty}
          emptyDescription={filteredEmpty ? OPERATIONAL_AUDIT_COPY.auditFilteredEmpty : undefined}
          onClearFilters={onClearFilters}
          getRowKey={(row) => row.eventId}
          onRowActivate={handleRowActivate}
          getRowClassName={(row) =>
            selectedEventId === row.eventId ? styles.selectedRow : undefined
          }
          cursorPagination={cursorPagination}
          loadingMore={loadingMore}
          enforceDomRowCap={false}
          variant="embedded"
        />
      </div>
    </section>
  );
}
