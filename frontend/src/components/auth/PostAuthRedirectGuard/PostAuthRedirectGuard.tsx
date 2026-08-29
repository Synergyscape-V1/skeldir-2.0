import { Navigate, useLocation } from 'react-router-dom';
import type { ReactNode } from 'react';
import { getAuthState } from '../../../auth/sessionStore';
import { defaultPostLoginPath, resolveSafeRedirect } from '../../../auth/redirectGuard';
import { UnsafeRedirectBanner } from '../AuthErrorBanner/AuthErrorBanner';

export interface PostAuthRedirectGuardProps {
  children: ReactNode;
  requireSession?: boolean;
  requireTenant?: boolean;
  fallback?: string;
}

export function PostAuthRedirectGuard({
  children,
  requireSession = false,
  requireTenant = false,
  fallback = defaultPostLoginPath(),
}: PostAuthRedirectGuardProps) {
  const location = useLocation();
  const { session, tenant } = getAuthState();
  const params = new URLSearchParams(location.search);
  const redirectParam = params.get('redirect');
  const resolution = resolveSafeRedirect(redirectParam, {
    hasSession: Boolean(session),
    hasTenant: Boolean(tenant),
  }, fallback);

  if (requireSession && !session) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  if (requireTenant && !tenant) {
    return <Navigate to="/signup" replace />;
  }

  if (redirectParam && !resolution.ok) {
    return (
      <>
        <UnsafeRedirectBanner />
        {children}
      </>
    );
  }

  if (redirectParam && resolution.ok && resolution.path !== location.pathname) {
    return <Navigate to={resolution.path} replace />;
  }

  return <>{children}</>;
}

export interface TenantCreationBoundaryProps {
  children: ReactNode;
}

export function TenantCreationBoundary({ children }: TenantCreationBoundaryProps) {
  return (
    <PostAuthRedirectGuard requireTenant fallback="/entry/workspace-created">
      {children}
    </PostAuthRedirectGuard>
  );
}
