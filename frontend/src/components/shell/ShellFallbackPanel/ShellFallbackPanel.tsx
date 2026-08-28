import { Link } from 'react-router-dom';
import { Card } from '../../layout/Card/Card';
import { Typography } from '../../layout/Typography/Typography';
import { RouteRecoveryPanel } from '../../../routeRecovery/RouteRecoveryPanel';
import { SHELL_COPY } from '../../../shell/copy';
import { getAuthState } from '../../../auth/sessionStore';
import type { ShellRoutePanelState } from '../../../shell/types';
import type { ShellNavItem } from '../../../shell/types';
import { useTimedCardLoading } from '../../../lib/loading';
import styles from './ShellFallbackPanel.module.css';

export interface ShellFallbackPanelProps {
  state: ShellRoutePanelState;
  navItem?: ShellNavItem;
  errorMessage?: string;
  onRetry?: () => void;
}

export function ShellFallbackPanel({ state, navItem, errorMessage, onRetry }: ShellFallbackPanelProps) {
  const timedLoading = useTimedCardLoading(state === 'loading', { onRetry });

  if (state === 'shell-landing') {
    return (
      <section className={styles.panel} data-shell-panel="landing" aria-labelledby="shell-landing-title">
        <Typography variant="h2" id="shell-landing-title">
          {SHELL_COPY.shellLandingTitle}
        </Typography>
        <p className={styles.body}>{SHELL_COPY.shellLandingBody}</p>
        <p className={styles.meta}>{SHELL_COPY.shellLandingNextStep}</p>
      </section>
    );
  }

  if (state === 'route-blocked' && navItem) {
    return (
      <section
        className={styles.panel}
        data-shell-panel="blocked"
        data-nav-id={navItem.id}
        aria-labelledby="shell-blocked-title"
      >
        <Typography variant="h2" id="shell-blocked-title">
          {SHELL_COPY.blockedRouteTitle(navItem.label)}
        </Typography>
        <p className={styles.body}>{SHELL_COPY.blockedRouteBody(navItem.unlockLabel)}</p>
        <p className={styles.meta}>{SHELL_COPY.blockedRouteInvariant}</p>
      </section>
    );
  }

  if (state === 'unknown-route') {
    return (
      <section className={styles.panel} data-shell-panel="unknown-route" aria-labelledby="shell-unknown-title">
        <RouteRecoveryPanel variant="authenticated" />
        <Typography variant="h2" id="shell-unknown-title">
          {SHELL_COPY.unknownRouteTitle}
        </Typography>
        <p className={styles.body}>{SHELL_COPY.unknownRouteBody}</p>
      </section>
    );
  }

  if (state === 'session-missing') {
    return (
      <section className={styles.panel} data-shell-panel="session-missing" aria-labelledby="shell-session-title">
        <Typography variant="h2" id="shell-session-title">
          {SHELL_COPY.sessionMissingTitle}
        </Typography>
        <p className={styles.body}>{SHELL_COPY.sessionMissingBody}</p>
        <Link to="/login">{SHELL_COPY.enterAppFrame}</Link>
      </section>
    );
  }

  if (state === 'tenant-missing') {
    const { session } = getAuthState();
    return (
      <section className={styles.panel} data-shell-panel="tenant-missing" aria-labelledby="shell-tenant-title">
        <Typography variant="h2" id="shell-tenant-title">
          {SHELL_COPY.tenantMissingTitle}
        </Typography>
        <p className={styles.body}>{SHELL_COPY.tenantMissingBody}</p>
        {session ? (
          <Link to="/signup">{SHELL_COPY.tenantMissingAction}</Link>
        ) : (
          <Link to="/login">{SHELL_COPY.enterAppFrame}</Link>
        )}
      </section>
    );
  }

  if (state === 'permission-denied') {
    return (
      <section className={styles.panel} data-shell-panel="permission-denied" role="alert">
        <Typography variant="h2">{SHELL_COPY.permissionDeniedTitle}</Typography>
        <p className={styles.body}>{SHELL_COPY.permissionDeniedBody}</p>
      </section>
    );
  }

  if (state === 'error') {
    return (
      <section className={styles.panel} data-shell-panel="error" role="alert">
        <Typography variant="h2">{SHELL_COPY.shellError}</Typography>
        {errorMessage ? <p className={styles.body}>{errorMessage}</p> : null}
      </section>
    );
  }

  if (!timedLoading) return null;

  return (
    <Card
      title={undefined}
      state={timedLoading.state}
      progressCopy={timedLoading.progressCopy}
      onRetry={timedLoading.onRetry}
    />
  );
}
