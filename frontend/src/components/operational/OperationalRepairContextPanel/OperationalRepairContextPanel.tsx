import { Card } from '../../layout/Card/Card';
import { OPERATIONAL_AUDIT_COPY } from '../../../operationalAudit/copy';
import styles from './OperationalRepairContextPanel.module.css';

export function OperationalRepairContextPanel() {
  return (
    <Card className={styles.panel} data-repair-context-panel>
      <h3 className={styles.title}>{OPERATIONAL_AUDIT_COPY.repairContextTitle}</h3>
      <p className={styles.body}>{OPERATIONAL_AUDIT_COPY.repairContextBody}</p>
    </Card>
  );
}
