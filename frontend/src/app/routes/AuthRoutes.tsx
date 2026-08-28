import { Link, Navigate, useSearchParams } from 'react-router-dom';
import { AUTH_COPY } from '../../auth/copy';
import { defaultShellPath } from '../../auth/redirectGuard';
import { getAuthState } from '../../auth/sessionStore';
import type { IdentityMode } from '../../auth/identityFlow';
import { AuthEntryFlow } from '../../components/auth/AuthEntryFlow/AuthEntryFlow';
import { Card } from '../../components/layout/Card/Card';
import { PageSurface } from '../../components/layout/PageSurface/PageSurface';
import styles from '../authPages.module.css';

function resolveInviteContext(searchParams: URLSearchParams) {
  const token = searchParams.get('token');
  const organizationName = searchParams.get('org');
  if (!token) return undefined;
  return { organizationName: organizationName ?? 'your organization' };
}

function resolveDefaultIdentityMode(pathname: string, searchParams: URLSearchParams): IdentityMode {
  if (pathname === '/signup' || searchParams.get('mode') === 'sign-up') {
    return 'sign-up';
  }
  return 'sign-in';
}

/**
 * Single auth identity entry surface — one modal, two in-place states (sign-in / sign-up).
 * `/login`, `/signup`, and `/auth` are route aliases that only set the initial toggle state.
 */
function AuthIdentityPage({ dataRoute }: { dataRoute: string }) {
  const [searchParams] = useSearchParams();
  const redirectTarget = searchParams.get('redirect');
  const inviteContext = resolveInviteContext(searchParams);
  const defaultIdentityMode = resolveDefaultIdentityMode(dataRoute, searchParams);

  return (
    <AuthEntryFlow
      defaultIdentityMode={defaultIdentityMode}
      inviteContext={inviteContext}
      redirectTarget={redirectTarget}
      dataRoute={dataRoute}
    />
  );
}

export function LoginPage() {
  return <AuthIdentityPage dataRoute="/login" />;
}

export function SignupPage() {
  return <AuthIdentityPage dataRoute="/signup" />;
}

export function AuthInvitePage() {
  return <AuthIdentityPage dataRoute="/auth" />;
}

export function SessionReadyPage() {
  const { session, tenant } = getAuthState();
  if (!session) {
    return <Navigate to="/login" replace />;
  }

  return (
    <PageSurface>
      <div className={styles.page} data-route="/entry/session-ready">
        <div className={styles.cardWrap}>
          <Card title={AUTH_COPY.handoffSessionTitle}>
            <p className={styles.handoffBody}>{AUTH_COPY.handoffSessionBody}</p>
            {tenant ? (
              <Link className={styles.enterShell} to={defaultShellPath()}>
                {AUTH_COPY.enterAppFrame}
              </Link>
            ) : (
              <p className={styles.meta}>Create an organization to enter the tenant-scoped app frame.</p>
            )}
          </Card>
        </div>
      </div>
    </PageSurface>
  );
}

export function WorkspaceCreatedPage() {
  const { session, tenant } = getAuthState();
  if (!session) return <Navigate to="/login" replace />;
  if (!tenant) return <Navigate to="/signup" replace />;

  return (
    <PageSurface>
      <div className={styles.page} data-route="/entry/workspace-created">
        <div className={styles.cardWrap}>
          <Card title={AUTH_COPY.handoffWorkspaceTitle}>
            <p className={styles.handoffBody}>{AUTH_COPY.handoffWorkspaceBody}</p>
            <Link className={styles.enterShell} to={defaultShellPath()}>
              {AUTH_COPY.enterAppFrame}
            </Link>
          </Card>
        </div>
      </div>
    </PageSurface>
  );
}
