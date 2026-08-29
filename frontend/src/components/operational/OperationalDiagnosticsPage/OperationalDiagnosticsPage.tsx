import { PageSurface } from '../../layout/PageSurface/PageSurface';
import { Typography } from '../../layout/Typography/Typography';
import { ErrorBanner } from '../../layout/ErrorBanner/ErrorBanner';
import { OPERATIONAL_AUDIT_COPY } from '../../../operationalAudit/copy';
import { useOperationalDiagnostics } from '../../../operationalAudit/useOperationalAudit';
import { PermissionDeniedPanel } from '../../governance/PermissionDeniedPanel/PermissionDeniedPanel';
import { OperationalDiagnosticSummary } from '../OperationalDiagnosticSummary/OperationalDiagnosticSummary';
import { DLQEventTable } from '../DLQEventTable/DLQEventTable';
import { OperationalRepairContextPanel } from '../OperationalRepairContextPanel/OperationalRepairContextPanel';
import styles from './OperationalDiagnosticsPage.module.css';

export function OperationalDiagnosticsPage() {
  const {
    payload,
    dlqEvents,
    loading,
    error,
    permissionDenied,
    empty,
    totalCount,
    offset,
    pageSize,
    hasMore,
    goToNextPage,
    goToPreviousPage,
    refresh,
  } = useOperationalDiagnostics();

  if (permissionDenied) {
    return (
      <PageSurface>
        <PermissionDeniedPanel />
      </PageSurface>
    );
  }

  return (
    <PageSurface data-operational-diagnostics-page>
      <header className={styles.header}>
        <Typography variant="h2">{OPERATIONAL_AUDIT_COPY.diagnosticsPageTitle}</Typography>
        <p className={styles.description}>{OPERATIONAL_AUDIT_COPY.diagnosticsPageDescription}</p>
      </header>
      {error && !loading ? <ErrorBanner variant="error" message={error} /> : null}
      <OperationalDiagnosticSummary summary={payload?.summary} loading={loading} />
      <DLQEventTable
        events={dlqEvents}
        loading={loading}
        error={error}
        empty={empty}
        onRetry={() => void refresh()}
        pagination={{
          totalCount,
          offset,
          pageSize,
          hasMore,
          onNext: goToNextPage,
          onPrevious: goToPreviousPage,
        }}
      />
      <OperationalRepairContextPanel />
    </PageSurface>
  );
}
