import { Navigate } from 'react-router-dom';

export function AuditAliasRedirect() {
  return <Navigate to="/app/audit" replace />;
}

export function DiagnosticsAliasRedirect() {
  return <Navigate to="/app/diagnostics" replace />;
}
