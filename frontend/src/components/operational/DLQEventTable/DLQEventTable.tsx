import { Table, type TableColumn, type TablePagination } from '../../layout/Table/Table';
import { OPERATIONAL_AUDIT_COPY } from '../../../operationalAudit/copy';
import { LOADING_COPY } from '../../../lib/copy';
import { useTimedTableLoading } from '../../../lib/loading';
import type { DLQEvent } from '../../../operationalAudit/types';
import { OperationalIssueStatusBadge } from '../OperationalIssueStatusBadge/OperationalIssueStatusBadge';
import styles from './DLQEventTable.module.css';

export interface DLQEventTableProps {
  events: DLQEvent[];
  loading?: boolean;
  error?: string;
  permissionDenied?: boolean;
  empty?: boolean;
  pagination?: TablePagination;
  onRetry?: () => void;
}

export function DLQEventTable({
  events,
  loading,
  error,
  permissionDenied,
  empty,
  pagination,
  onRetry,
}: DLQEventTableProps) {
  const columns: TableColumn<DLQEvent>[] = [
    {
      key: 'occurredAt',
      header: 'Time',
      render: (row) => new Date(row.occurredAt).toLocaleString(),
    },
    {
      key: 'queue',
      header: 'Queue',
      render: (row) => row.queueName,
    },
    {
      key: 'task',
      header: 'Task type',
      render: (row) => row.taskType,
    },
    {
      key: 'status',
      header: 'Status',
      render: (row) => (
        <span className={styles.status} data-dlq-status={row.status}>
          {row.status.replace('_', ' ')}
        </span>
      ),
    },
    {
      key: 'issue',
      header: 'Issue',
      render: (row) => <OperationalIssueStatusBadge kind={row.issueKind} />,
    },
    {
      key: 'summary',
      header: 'Summary',
      render: (row) => row.summary,
    },
  ];

  const timedLoading = useTimedTableLoading(!!loading, { progressCopy: LOADING_COPY.progress, onRetry });

  let state: import('../../layout/Table/Table').TableState = 'populated';
  if (permissionDenied) state = 'permission_denied';
  else if (error) state = 'error';
  else if (timedLoading) state = timedLoading.state;
  else if (empty) state = 'empty';

  return (
    <div data-dlq-event-table>
      <Table
        caption={OPERATIONAL_AUDIT_COPY.dlqTableCaption}
        columns={columns}
        rows={events}
        state={state}
        progressCopy={timedLoading?.progressCopy}
        onRetry={timedLoading?.onRetry}
        errorMessage={error}
        emptyTitle={OPERATIONAL_AUDIT_COPY.diagnosticEmpty}
        getRowKey={(row) => row.eventId}
        pagination={pagination}
      />
    </div>
  );
}
