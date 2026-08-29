import type { AuditActivityTone } from '../../../commandCenter/types';
import policyIcon from '../../../assets/icons/status/policy.svg';
import { WarningSignalIcon } from '../WarningSignalIcon/WarningSignalIcon';
import { BenchmarkTransitionMark } from './BenchmarkTransitionMark';
import styles from './AuditActivityIcon.module.css';

export function AuditActivityIcon({ tone }: { tone: AuditActivityTone }) {
  if (tone === 'info' || tone === 'success') {
    return (
      <span className={[styles.root, styles.imgTone, styles[`tone_${tone}`]].join(' ')} data-audit-activity-icon={tone} aria-hidden="true">
        <img src={policyIcon} alt="" width={20} height={20} className={styles.imgIcon} />
      </span>
    );
  }

  if (tone === 'error') {
    return (
      <WarningSignalIcon
        className={[styles.root, styles.tone_error].join(' ')}
        data-audit-activity-icon={tone}
      />
    );
  }

  return (
    <span className={[styles.root, styles.signal, styles.tone_refresh].join(' ')} data-audit-activity-icon={tone} aria-hidden="true">
      <BenchmarkTransitionMark className={styles.icon} />
    </span>
  );
}
