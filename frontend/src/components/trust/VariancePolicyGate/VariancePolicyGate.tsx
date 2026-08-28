import { IconInfo, IconWarning } from '../../icons/StatusIcons';
import {
  resolveDiscrepancyPresentation,
  type DiscrepancyPresentationInput,
} from '../../../claims/discrepancySemantics';
import styles from './VariancePolicyGate.module.css';

export interface VariancePolicyGateProps extends DiscrepancyPresentationInput {}

export function VariancePolicyGate(props: VariancePolicyGateProps) {
  const presentation = resolveDiscrepancyPresentation(props);

  if ('error' in presentation) {
    return (
      <span role="alert" data-variance-policy-gate="error">
        {presentation.error}
      </span>
    );
  }

  const toneClass = presentation.varianceGateTone === 'info' ? styles.info : styles.warning;
  const Icon = presentation.varianceGateLocked ? IconWarning : IconInfo;

  return (
    <span
      className={[styles.gate, toneClass].join(' ')}
      data-variance-policy-gate
      data-variance-gate-locked={presentation.varianceGateLocked ? 'true' : 'false'}
      data-variance-action-blocked={presentation.varianceGateLocked ? 'true' : 'false'}
      role="status"
      aria-live="polite"
    >
      <Icon aria-hidden="true" className={styles.icon} />
      <span className={styles.label}>{presentation.varianceGateLabel}</span>
    </span>
  );
}
