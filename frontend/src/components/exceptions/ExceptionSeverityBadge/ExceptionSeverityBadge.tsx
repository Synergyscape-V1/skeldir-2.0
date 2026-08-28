import type { ExceptionSeverity } from '../../../ledger/types';
import { EXCEPTION_SEVERITY_LABELS } from '../../../exceptions/copy';
import statusText from '../../../styles/trustStatusText.module.css';
import { trustChipClassNames, type TrustChipTone } from '../../trust/TrustChip/TrustChip';

const SEVERITY_TONE: Record<ExceptionSeverity, TrustChipTone> = {
  critical: 'error',
  warning: 'warning',
  info: 'info',
};

const TABLE_SEVERITY_LABELS: Record<ExceptionSeverity, string> = {
  critical: 'Critical',
  warning: 'Warning',
  info: 'Info',
};

const TABLE_SEVERITY_TEXT_LABELS: Record<ExceptionSeverity, string> = {
  critical: 'Critical',
  warning: 'Warning',
  info: 'Info',
};

const TONE_TEXT_CLASS: Record<TrustChipTone, string> = {
  success: statusText.labelSuccess,
  warning: statusText.labelWarning,
  error: statusText.labelError,
  info: statusText.labelInfo,
  neutral: statusText.labelNeutral,
  probabilistic: statusText.labelProbabilistic,
  benchmark: statusText.labelBenchmark,
  deterministic: statusText.labelSuccess,
};

type ExceptionBadgeOptions = {
  variant?: 'chip' | 'text';
  table?: boolean;
  compact?: boolean;
};

export function ExceptionSeverityBadge({
  severity,
  variant = 'chip',
}: { severity: ExceptionSeverity } & ExceptionBadgeOptions) {
  const tone = SEVERITY_TONE[severity];
  const className = variant === 'text' ? TONE_TEXT_CLASS[tone] : trustChipClassNames(tone);
  const displayLabel = variant === 'text' ? TABLE_SEVERITY_TEXT_LABELS[severity] : TABLE_SEVERITY_LABELS[severity];

  return (
    <span
      className={className}
      {...(variant === 'text' ? { 'data-status-text': true } : { 'data-trust-chip': true })}
      data-exception-severity={severity}
      title={EXCEPTION_SEVERITY_LABELS[severity]}
      role="status"
    >
      {displayLabel}
    </span>
  );
}
