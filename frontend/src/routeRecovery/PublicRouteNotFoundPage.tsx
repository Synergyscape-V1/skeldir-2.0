import { Link } from 'react-router-dom';
import { PageSurface } from '../components/layout/PageSurface/PageSurface';
import { Typography } from '../components/layout/Typography/Typography';
import { ROUTE_RECOVERY_COPY } from './copy';
import shared from '../styles/shared.module.css';
import styles from './PublicRouteNotFoundPage.module.css';

export function PublicRouteNotFoundPage() {
  return (
    <PageSurface data-public-route-not-found>
      <section className={styles.panel} role="alert" aria-labelledby="public-not-found-title">
        <Typography variant="h1" id="public-not-found-title">
          {ROUTE_RECOVERY_COPY.notFoundTitle}
        </Typography>
        <p className={styles.body}>{ROUTE_RECOVERY_COPY.publicNotFoundBody}</p>
        <Link to="/login" className={[styles.actionLink, shared.focusVisible].join(' ')} data-route-recovery-login>
          {ROUTE_RECOVERY_COPY.returnToLogin}
        </Link>
      </section>
    </PageSurface>
  );
}
