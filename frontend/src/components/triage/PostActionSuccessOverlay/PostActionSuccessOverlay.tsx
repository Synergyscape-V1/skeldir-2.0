import { Link } from 'react-router-dom';

import { COMMAND_CENTER_COPY } from '../../../commandCenter/copy';
import shared from '../../../styles/shared.module.css';
import styles from './PostActionSuccessOverlay.module.css';

export type PostActionOverlayMode = 'advance' | 'cleared';

export interface PostActionSuccessOverlayProps {
  open: boolean;
  mode: PostActionOverlayMode;
  onReturnToDashboard?: () => void;
}

export function PostActionSuccessOverlay({
  open,
  mode,
  onReturnToDashboard,
}: PostActionSuccessOverlayProps) {
  if (!open) return null;

  if (mode === 'cleared') {
    return (
      <div className={styles.overlay} data-post-action-overlay data-post-action-mode="cleared" role="status" aria-live="assertive">
        <div className={styles.panel}>
          <span className={styles.check} aria-hidden="true">
            ✓
          </span>
          <h2 className={styles.headline}>{COMMAND_CENTER_COPY.triage.allClearHeadline}</h2>
          <p className={styles.subcopy}>{COMMAND_CENTER_COPY.triage.allClearSubcopy}</p>
          <Link
            to="/app"
            className={[styles.cta, shared.focusVisible].join(' ')}
            data-post-action-return-dashboard
            onClick={onReturnToDashboard}
          >
            {COMMAND_CENTER_COPY.triage.returnToDashboard}
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.overlay} data-post-action-overlay data-post-action-mode="advance" role="status" aria-live="assertive">
      <div className={styles.panel}>
        <span className={styles.check} aria-hidden="true">
          ✓
        </span>
        <h2 className={styles.headline}>{COMMAND_CENTER_COPY.triage.successHeadline}</h2>
        <p className={styles.subcopy}>{COMMAND_CENTER_COPY.triage.successSubcopy}</p>
      </div>
    </div>
  );
}
