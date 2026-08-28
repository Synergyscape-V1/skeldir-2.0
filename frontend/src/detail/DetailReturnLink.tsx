import { Link, useLocation } from 'react-router-dom';
import { buildParentReturnLink, resolveParentContext } from './parentContext';
import { truncateIdentifier } from '../lib/truncateIdentifier';
import shared from '../styles/shared.module.css';
import styles from './DetailReturnLink.module.css';

export interface DetailReturnLinkProps {
  surface: 'claims' | 'trust' | 'channels' | 'budget' | 'exceptions';
}

type DetailLocationState = {
  parentSearch?: string;
  fromCommandCenterRecent?: boolean;
  recentSubjectRef?: string;
};

export function DetailReturnLink({ surface }: DetailReturnLinkProps) {
  const location = useLocation();
  const state = (location.state as DetailLocationState | null) ?? {};
  const parentSearch = state.parentSearch ?? '';
  const ctx = resolveParentContext(surface, parentSearch);

  if (state.fromCommandCenterRecent) {
    const subjectLabel = state.recentSubjectRef
      ? truncateIdentifier(state.recentSubjectRef)
      : 'TrustEnvelope';

    return (
      <nav className={styles.breadcrumb} aria-label="Breadcrumb" data-trust-detail-breadcrumb>
        <Link to="/app" className={[styles.breadcrumbLink, shared.focusVisible].join(' ')}>
          Command Center
        </Link>
        <span className={styles.breadcrumbSep} aria-hidden>
          /
        </span>
        <Link to="/app" className={[styles.breadcrumbLink, shared.focusVisible].join(' ')}>
          Recent
        </Link>
        <span className={styles.breadcrumbSep} aria-hidden>
          /
        </span>
        <span className={styles.breadcrumbCurrent} title={state.recentSubjectRef}>
          {subjectLabel}
        </span>
      </nav>
    );
  }

  return (
    <Link
      to={buildParentReturnLink(ctx)}
      className={[styles.link, shared.focusVisible].join(' ')}
      data-detail-return-link
    >
      {ctx.returnLabel}
      {parentSearch ? <span className={styles.srOnly}> with preserved filters</span> : null}
    </Link>
  );
}
