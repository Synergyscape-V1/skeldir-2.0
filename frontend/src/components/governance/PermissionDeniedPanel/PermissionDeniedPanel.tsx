import { Link } from 'react-router-dom';
import { GOVERNANCE_COPY } from '../../../governance/copy';
import { Card } from '../../layout/Card/Card';
import { Typography } from '../../layout/Typography/Typography';
import shared from '../../../styles/shared.module.css';
import styles from './PermissionDeniedPanel.module.css';

export interface PermissionDeniedPanelProps {
  recoveryHref?: string;
}

export function PermissionDeniedPanel({ recoveryHref = '/app' }: PermissionDeniedPanelProps) {
  return (
    <Card data-permission-denied-panel>
      <div className={styles.panel} role="alert">
        <Typography variant="h3">{GOVERNANCE_COPY.permissionDeniedTitle}</Typography>
        <p className={styles.body}>{GOVERNANCE_COPY.permissionDeniedBody}</p>
        <Link to={recoveryHref} className={[styles.recovery, shared.focusVisible].join(' ')}>
          {GOVERNANCE_COPY.permissionDeniedRecovery}
        </Link>
      </div>
    </Card>
  );
}
