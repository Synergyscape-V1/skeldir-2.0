import type { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { getAuthState } from '../../../auth/sessionStore';
import { TimedLoadingPanel } from '../../../lib/loading';
import { ShellFallbackPanel } from '../ShellFallbackPanel/ShellFallbackPanel';

export interface ShellAccessGuardProps {
  children: ReactNode;
  /** Test-only override to simulate guard states */
  forceState?: 'loading' | 'session-missing' | 'tenant-missing';
}

export function ShellAccessGuard({ children, forceState }: ShellAccessGuardProps) {
  const { session, tenant, bootstrapStatus } = getAuthState();
  const isLoading =
    forceState === 'loading' || bootstrapStatus === 'loading' || bootstrapStatus === 'unknown';

  if (isLoading) {
    return (
      <div data-shell-guard="loading" aria-busy="true" aria-live="polite">
        <TimedLoadingPanel active />
      </div>
    );
  }

  if (forceState === 'session-missing' || !session) {
    return <Navigate to="/login?reason=session_required" replace />;
  }

  if (forceState === 'tenant-missing') {
    return (
      <div data-shell-guard="tenant-missing">
        <ShellFallbackPanel state="tenant-missing" />
      </div>
    );
  }

  if (!tenant) {
    return <Navigate to="/signup" replace />;
  }

  return <>{children}</>;
}
