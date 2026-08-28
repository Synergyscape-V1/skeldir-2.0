import { Link, useInRouterContext, useLocation } from 'react-router-dom';
import shared from '../styles/shared.module.css';
import styles from './DetailNavigationAffordance.module.css';

export interface DetailNavigationAffordanceProps {
  surfaceLabel: string;
  rowIdentity: string;
  detailPath: string;
  disabled?: boolean;
}

function DetailNavigationLink({
  surfaceLabel,
  rowIdentity,
  detailPath,
}: Omit<DetailNavigationAffordanceProps, 'disabled'>) {
  const location = useLocation();

  return (
    <Link
      to={detailPath}
      state={{ parentSearch: location.search }}
      className={[styles.button, shared.focusVisible].join(' ')}
      data-detail-affordance="navigate"
      aria-label={`View ${surfaceLabel} for ${rowIdentity}`}
    >
      View detail
    </Link>
  );
}

export function DetailNavigationAffordance({
  surfaceLabel,
  rowIdentity,
  detailPath,
  disabled = false,
}: DetailNavigationAffordanceProps) {
  if (disabled) {
    return (
      <button
        type="button"
        className={styles.button}
        disabled
        data-detail-affordance="navigate"
        aria-label={`View ${surfaceLabel} for ${rowIdentity}`}
      >
        View detail
      </button>
    );
  }

  if (useInRouterContext()) {
    return (
      <DetailNavigationLink
        surfaceLabel={surfaceLabel}
        rowIdentity={rowIdentity}
        detailPath={detailPath}
      />
    );
  }

  return (
    <a
      href={detailPath}
      className={[styles.button, shared.focusVisible].join(' ')}
      data-detail-affordance="navigate"
      aria-label={`View ${surfaceLabel} for ${rowIdentity}`}
    >
      View detail
    </a>
  );
}
