import { Link } from 'react-router-dom';
import { getAuthState } from '../auth/sessionStore';
import { Typography } from '../components/layout/Typography/Typography';
import { ROUTE_RECOVERY_COPY } from './copy';
import shared from '../styles/shared.module.css';
import styles from './RouteRecoveryPanel.module.css';

export interface RouteRecoveryPanelProps {
  variant: 'authenticated' | 'tenant_missing' | 'restricted';
}

export function RouteRecoveryPanel({ variant }: RouteRecoveryPanelProps) {
  const { session, tenant } = getAuthState();
  const canReturnToCommandCenter = Boolean(session && tenant);

  return (
    <section
      className={styles.panel}
      data-route-recovery-panel
      data-route-recovery-variant={variant}
      role="alert"
      aria-labelledby="route-recovery-title"
    >
      <Typography variant="h2" id="route-recovery-title">
        {ROUTE_RECOVERY_COPY.notFoundTitle}
      </Typography>
      <p className={styles.body}>
        {variant === 'tenant_missing'
          ? ROUTE_RECOVERY_COPY.noTenantBody
          : ROUTE_RECOVERY_COPY.notFoundBody}
      </p>
      <nav className={styles.actions} aria-label="Route recovery actions">
        {canReturnToCommandCenter ? (
          <Link to="/app" className={[styles.actionLink, shared.focusVisible].join(' ')} data-route-recovery-command-center>
            {ROUTE_RECOVERY_COPY.returnToCommandCenter}
          </Link>
        ) : null}
        {variant === 'tenant_missing' ? (
          <Link to="/signup" className={[styles.actionLink, shared.focusVisible].join(' ')} data-route-recovery-signup>
            {ROUTE_RECOVERY_COPY.createWorkspace}
          </Link>
        ) : null}
        {!session ? (
          <Link to="/login" className={[styles.actionLink, shared.focusVisible].join(' ')} data-route-recovery-login>
            {ROUTE_RECOVERY_COPY.returnToLogin}
          </Link>
        ) : null}
        {session && tenant ? (
          <Link
            to="/app/settings/team"
            className={[styles.secondaryLink, shared.focusVisible].join(' ')}
            data-route-recovery-settings
          >
            {ROUTE_RECOVERY_COPY.returnToSettings}
          </Link>
        ) : null}
      </nav>
    </section>
  );
}
