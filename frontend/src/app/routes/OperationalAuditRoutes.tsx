import { Routes, Route } from 'react-router-dom';
import { Level5RouteGuard } from '../../components/operational/Level5RouteGuard/Level5RouteGuard';
import { OperationalDiagnosticsPage } from '../../components/operational/OperationalDiagnosticsPage/OperationalDiagnosticsPage';
import { AuditLedgerPage } from '../../components/audit/AuditLedgerPage/AuditLedgerPage';
import { AuditForensicEventDetailPage } from '../../components/audit/AuditForensicEventDetailPage/AuditForensicEventDetailPage';

export function AuditLedgerRoute() {
  return (
    <Level5RouteGuard>
      <Routes>
        <Route index element={<AuditLedgerPage />} />
        <Route path="events/:eventId" element={<AuditForensicEventDetailPage />} />
      </Routes>
    </Level5RouteGuard>
  );
}

export function OperationalDiagnosticsRoute() {
  return (
    <Level5RouteGuard>
      <OperationalDiagnosticsPage />
    </Level5RouteGuard>
  );
}
