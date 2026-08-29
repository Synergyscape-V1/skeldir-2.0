import type { AuditLogMode } from '../../../operationalAudit/types';
import { OPERATIONAL_AUDIT_COPY } from '../../../operationalAudit/copy';
import styles from './AuditLogModeSwitch.module.css';

export interface AuditLogModeSwitchProps {
  value: AuditLogMode;
  onChange: (mode: AuditLogMode) => void;
}

export function AuditLogModeSwitch({ value, onChange }: AuditLogModeSwitchProps) {
  return (
    <fieldset className={styles.switch} data-audit-log-mode-switch>
      <legend className={styles.legend}>{OPERATIONAL_AUDIT_COPY.auditLogModeLabel}</legend>
      <div className={styles.options} role="radiogroup" aria-label={OPERATIONAL_AUDIT_COPY.auditLogModeLabel}>
        <label className={styles.option}>
          <input
            type="radio"
            name="audit-log-mode"
            value="forensic_log"
            checked={value === 'forensic_log'}
            onChange={() => onChange('forensic_log')}
          />
          <span className={styles.optionBody}>
            <span className={styles.optionTitle}>{OPERATIONAL_AUDIT_COPY.auditLogModeForensic}</span>
            <span className={styles.optionDescription}>
              {OPERATIONAL_AUDIT_COPY.auditLogModeForensicDescription}
            </span>
          </span>
        </label>
        <label className={styles.option}>
          <input
            type="radio"
            name="audit-log-mode"
            value="access_history"
            checked={value === 'access_history'}
            onChange={() => onChange('access_history')}
          />
          <span className={styles.optionBody}>
            <span className={styles.optionTitle}>{OPERATIONAL_AUDIT_COPY.auditLogModeAccess}</span>
            <span className={styles.optionDescription}>
              {OPERATIONAL_AUDIT_COPY.auditLogModeAccessDescription}
            </span>
          </span>
        </label>
      </div>
    </fieldset>
  );
}
