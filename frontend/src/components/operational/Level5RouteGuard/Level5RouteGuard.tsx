import type { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { getAuthState } from '../../../auth/sessionStore';
import { ErrorBanner } from '../../layout/ErrorBanner/ErrorBanner';

export interface Level5RouteGuardProps {
  children: ReactNode;
}

export function Level5RouteGuard({ children }: Level5RouteGuardProps) {
  const { session, tenant } = getAuthState();

  if (!session) {
    return <Navigate to="/login" replace />;
  }

  if (!tenant) {
    return (
      <ErrorBanner
        variant="error"
        message="Tenant context required for operational and audit surfaces."
      />
    );
  }

  return <>{children}</>;
}
