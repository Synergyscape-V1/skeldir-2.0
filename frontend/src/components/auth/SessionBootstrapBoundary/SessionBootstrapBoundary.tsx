import { useEffect, useState, type ReactNode } from 'react';
import type { AuthClient } from '../../../auth/authClient';
import { createMockTenant, getDefaultAuthClient } from '../../../auth/authClient';
import { mapAuthOutcomeToMessage } from '../../../auth/outcomeMapping';
import type { AuthOutcome } from '../../../auth/types';
import type { ProductAuthState } from '../../../auth/sessionStore';
import {
  establishSession,
  establishTenant,
  getAuthState,
  setBootstrapLoading,
  setBootstrapReady,
  subscribeAuthState,
} from '../../../auth/sessionStore';
import {
  isDesignSprintAuthEnabled,
  readPersistedDesignSprintAuth,
} from '../../../auth/designSprintAuth';
import { Skeleton } from '../../layout/Skeleton/Skeleton';
import { AuthErrorBanner } from '../AuthErrorBanner/AuthErrorBanner';

export interface SessionBootstrapBoundaryProps {
  children: ReactNode;
  authClient?: AuthClient;
}

export function SessionBootstrapBoundary({
  children,
  authClient = getDefaultAuthClient(),
}: SessionBootstrapBoundaryProps) {
  const [status, setStatus] = useState(getAuthState().bootstrapStatus);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    return subscribeAuthState((next: ProductAuthState) => setStatus(next.bootstrapStatus));
  }, []);

  useEffect(() => {
    if (status !== 'unknown') return;

    if (isDesignSprintAuthEnabled()) {
      const persisted = readPersistedDesignSprintAuth();
      if (persisted) {
        setBootstrapLoading();
        if (persisted.tenant) {
          establishTenant(persisted.session, persisted.tenant, persisted.user);
        } else if (persisted.session.tenantId) {
          establishTenant(
            persisted.session,
            createMockTenant({ tenantId: persisted.session.tenantId }),
            persisted.user,
          );
        } else {
          establishSession(persisted.session, null, persisted.user);
        }
        return;
      }
    }

    setBootstrapLoading();
    void authClient.validateSession().then((outcome: AuthOutcome | { kind: 'no_session' }) => {
      if (outcome.kind === 'no_session') {
        setBootstrapReady();
        return;
      }
      if (outcome.kind === 'success_session_established') {
        establishSession(outcome.session);
        return;
      }
      if (outcome.kind === 'session_expired') {
        setBootstrapReady();
        return;
      }
      setError(mapAuthOutcomeToMessage(outcome));
      setBootstrapReady();
    });
  }, [authClient, status]);

  if (status === 'unknown' || status === 'loading') {
    return <Skeleton variant="block" aria-label="Loading session state" />;
  }

  if (error) {
    return <AuthErrorBanner message={error} />;
  }

  return <>{children}</>;
}
